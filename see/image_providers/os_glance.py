# Copyright 2015-2016 F-Secure

# Licensed under the Apache License, Version 2.0 (the "License"); you
# may not use this file except in compliance with the License.  You may
# obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.  See the License for the specific language governing
# permissions and limitations under the License.
"""Glance image provider.

This provider retrieves the requested image from an OpenStack Glance service if
it doesn't already exist on the configured target path. Images can be requested
by name or UUID; if name is requested the latest matching image is retrieved.

provider_parameters:
    target_path (str): Absolute path where to download the image. If target_path
                       is a directory, the image's UUID will be used as filename.
    glance_url (str):  The URL of the OpenStack Glance service to query for the
                       images.
    os_auth (dict):    A dictionary with OpenStack authentication parameters as
                       needed by OpenStack's Keystone client.

"""

import os

from datetime import datetime
from see.interfaces import ImageProvider

try:
    FileNotFoundError
except NameError:
    FileNotFoundError = IOError


class GlanceProvider(ImageProvider):

    def __init__(self, parameters):
        super(GlanceProvider, self).__init__(parameters)
        self._keystone_client = None
        self._glance_client = None

    @property
    def image(self):
        metadata = self._image_metadata()
        if (os.path.exists(self.configuration['target_path']) and
                os.path.isfile(self.configuration['target_path'])):
            img_time = (datetime.strptime(metadata.updated_at,
                                          "%Y-%m-%dT%H:%M:%SZ") -
                        datetime(1970, 1, 1)).total_seconds()

            if os.path.getmtime(self.configuration['target_path']) > img_time:
                return self.configuration['target_path']

        self._download_from_glance(metadata)
        return ('/'.join((self.configuration['target_path'].rstrip('/'),
                          metadata.id))
                if os.path.isdir(self.configuration['target_path'])
                else self.configuration['target_path'])

    @property
    def _token(self):
        self.keystone_client.authenticate()
        return self.keystone_client.get_token(self.keystone_client.session)

    @property
    def keystone_client(self):
        if self._keystone_client is None:
            from keystoneclient.client import Client as Kclient
            self._keystone_client = Kclient(self.configuration['os_auth'])
        return self._keystone_client

    @property
    def glance_client(self):
        if self._glance_client is None:
            from glanceclient.v2.client import Client as Gclient
            self._glance_client = Gclient(
                self.configuration['glance_url'], token=self._token)
        return self._glance_client

    def _image_metadata(self):
        try:
            return sorted([image for image in self.glance_client.images.list()
                           if image.id == self.uri or image.name == self.uri],
                          key=lambda x: x.updated_at, reverse=True)[0]
        except IndexError:
            raise FileNotFoundError(self.uri)

    def _download_from_glance(self, img_metadata):
        img_downloader = self.glance_client.images.data(img_metadata.id)
        with open(self.configuration['target_path'], 'wb') as imagefile:
            for chunk in img_downloader:
                imagefile.write(chunk)
