import logging
import httplib
import urllib
import xmltodict
from six.moves.urllib_parse import urlparse

from . import discovery
from .util import deserialize_apps

try:
    from urllib.parse import quote_plus
except ImportError:
    from urllib import quote_plus


__version__ = '3.0.0'


COMMANDS = {
    # Standard Keys
    'home': 'Home',
    'reverse': 'Rev',
    'forward': 'Fwd',
    'play': 'Play',
    'select': 'Select',
    'left': 'Left',
    'right': 'Right',
    'down': 'Down',
    'up': 'Up',
    'back': 'Back',
    'replay': 'InstantReplay',
    'info': 'Info',
    'backspace': 'Backspace',
    'search': 'Search',
    'enter': 'Enter',
    'literal': 'Lit',

    # For devices that support "Find Remote"
    'find_remote': 'FindRemote',

    # For Roku TV
    'volume_down': 'VolumeDown',
    'volume_up': 'VolumeUp',
    'volume_mute': 'VolumeMute',

    # For Roku TV while on TV tuner channel
    'channel_up': 'ChannelUp',
    'channel_down': 'ChannelDown',

    # For Roku TV current input
    'input_tuner': 'InputTuner',
    'input_hdmi1': 'InputHDMI1',
    'input_hdmi2': 'InputHDMI2',
    'input_hdmi3': 'InputHDMI3',
    'input_hdmi4': 'InputHDMI4',
    'input_av1': 'InputAV1',

    # For devices that support being turned on/off
    'power': 'Power',
}

SENSORS = ('acceleration', 'magnetic', 'orientation', 'rotation')

TOUCH_OPS = ('up', 'down', 'press', 'move', 'cancel')


roku_logger = logging.getLogger('roku')


class RokuException(Exception):
    pass


class Application(object):

    def __init__(self, id, version, name, roku=None):
        self.id = str(id)
        self.version = version
        self.name = name
        self.roku = roku

    def __eq__(self, other):
        return isinstance(other, Application) and \
            (self.id, self.version) == (other.id, other.version)

    def __repr__(self):
        return ('<Application: [%s] %s v%s>' %
                (self.id, self.name, self.version))

    @property
    def icon(self):
        if self.roku:
            return self.roku.icon(self)

    def launch(self):
        if self.roku:
            self.roku.launch(self)

    def store(self):
        if self.roku:
            self.roku.store(self)


class DeviceInfo(object):

    def __init__(self, model_name, model_num, software_version, serial_num, user_device_name):
        self.model_name = model_name
        self.model_num = model_num
        self.software_version = software_version
        self.serial_num = serial_num
        self.user_device_name = user_device_name

    def __repr__(self):
        return ('<Device: %s Info: %s-%s, SW v%s, Ser# %s>' %
                (self.user_device_name, self.model_name, self.model_num,
                 self.software_version, self.serial_num))


class Roku(object):

    @classmethod
    def discover(self, *args, **kwargs):
        rokus = []
        for device in discovery.discover(*args, **kwargs):
            o = urlparse(device.location)
            rokus.append(Roku(o.hostname, o.port))
        return rokus

    def __init__(self, host, port=8060):
        self.host = host
        self.port = port
        self._conn = None

    def __repr__(self):
        return "<Roku: %s:%s>" % (self.host, self.port)

    def __getattr__(self, name):

        if name not in COMMANDS and name not in SENSORS:
            raise AttributeError('%s is not a valid method' % name)

        def command(*args):
            if name in SENSORS:
                keys = ['%s.%s' % (name, axis) for axis in ('x', 'y', 'z')]
                params = dict(zip(keys, args))
                self.input(params)
            elif name == 'literal':
                for char in args[0]:
                    path = '/keypress/%s_%s' % (COMMANDS[name], quote_plus(char))
                    self._post(path)
            else:
                path = '/keypress/%s' % COMMANDS[name]
                self._post(path)

        return command

    def __getitem__(self, key):
        key = str(key)
        app = self._app_for_name(key)
        if not app:
            app = self._app_for_id(key)
        return app

    def _app_for_name(self, name):
        lname = name.lower()
        for app in self.apps:
            if app.name == lname:
                return app

    def _app_for_id(self, app_id):
        lapp_id = app_id
        for app in self.apps:
            if app.id == lapp_id:
                return app

    def _get(self, path, params = ''):
        return self._call('GET', path, params)

    def _post(self, path, params = ''):
        return self._call('POST', path, params)

    def _call(self, method, path, params = ''):
        if method not in ('GET', 'POST'):
            raise ValueError('only GET and POST HTTP methods are supported')
        conn = httplib.HTTPConnection(self.host, self.port)
        conn.request(method, path, urllib.urlencode(params));
        resp = conn.getresponse()
        msg = resp.read()
        conn.close()
        if resp.status != 200:
            raise RokuException(msg)

        return msg

    @property
    def apps(self):
        resp = self._get('/query/apps')
        applications = deserialize_apps(resp)
        for a in applications:
            a.roku = self
        return applications

    @property
    def active_app(self):
        resp = self._get('/query/active-app')
        active_app = deserialize_apps(resp)
        if len(active_app):
            return active_app[0]
        else:
            return None

    @property
    def device_info(self):
        resp = self._get('/query/device-info')
        root = xmltodict.parse(resp)['device-info']

        dinfo = DeviceInfo(
            model_name=root['model-name'].encode('UTF-8'),
            model_num=root['model-number'].encode('UTF-8'),
            user_device_name=root['user-device-name'].encode('UTF-8'),
            software_version=''.join([
                root['software-version'].encode('UTF-8'),
                '.',
                root['software-build'].encode('UTF-8')
            ]),
            serial_num=root['serial-number'].encode('UTF-8')
        )
        return dinfo

    @property
    def commands(self):
        return sorted(COMMANDS.keys())

    def icon(self, app):
        return self._get('/query/icon/%s' % app.id)

    def launch(self, app):
        if app.roku and app.roku != self:
            raise RokuException('this app belongs to another Roku')
        return self._post('/launch/%s' % app.id, {'contentID': app.id})

    def store(self, app):
        return self._post('/launch/11', {'contentID': app.id})

    def input(self, params):
        return self._post('/input', params)

    def touch(self, x, y, op='down'):

        if op not in TOUCH_OPS:
            raise RokuException('%s is not a valid touch operation' % op)

        params = {
            'touch.0.x': x,
            'touch.0.y': y,
            'touch.0.op': op,
        }

        self.input(params)

    @property
    def current_app(self):
        resp = self._get('/query/active-app')
        root = ET.fromstring(resp)

        app_node = root.find('screensaver')
        if app_node is None:
            app_node = root.find('app')

        if app_node is None:
            return None

        return Application(
            id=app_node.get('id'),
            version=app_node.get('version'),
            name=app_node.text,
            roku=self,
        )
