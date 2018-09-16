# from contextlib import closing

import xmltodict
# from six import BytesIO


def deserialize_apps(doc, roku=None):

    from .core import Application

    applications = []
    root = xmltodict.parse(doc)['apps']['app']
    for elem in root:
        app = Application(
            id=elem['@id'].encode('UTF-8').lower(), version=elem['@version'].encode('UTF-8'), name=elem['#text'].encode('UTF-8').lower())
        applications.append(app)
    return applications


# def serialize_apps(apps):
#
#     root = ET.Element('apps')
#
#     for app in apps:
#         attrs = {'id': app.id, 'version': app.version}
#         elem = ET.SubElement(root, 'app', attrs)
#         elem.text = app.name
#
#     with closing(BytesIO()) as bffr:
#         tree = ET.ElementTree(root)
#         tree.write(bffr, xml_declaration=True, encoding="utf-8")
#         content = bffr.getvalue()
#
#     return content
