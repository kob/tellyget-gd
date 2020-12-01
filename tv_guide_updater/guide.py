import json
from xml.dom import minidom

import os
import re
from bs4 import BeautifulSoup


class Guide:
    def __init__(self, config, session, base_url, get_channels_data):
        self.config = config
        self.session = session
        self.base_url = base_url
        self.get_channels_data = get_channels_data

    def get_channels(self):
        response = self.session.post(self.base_url + '/EPG/jsp/getchannellistHWCTC.jsp', data=self.get_channels_data)
        soup = BeautifulSoup(response.text, 'html.parser')
        scripts = soup.find_all('script', string=re.compile('ChannelID=".+?"'))
        channels = []
        for script in scripts:
            match = re.search(r'Authentication.CTCSetConfig\(\'Channel\',\'(.+?)\'\)', script.string, re.MULTILINE)
            channel_params = match.group(1)
            channel = {}
            for channel_param in channel_params.split(','):
                pair = channel_param.split('=')
                key = pair[0]
                value = pair[1]
                value = value[1:len(value) - 1]
                channel[key] = value
            channels.append(channel)
        return channels

    def get_playlist(self, channels):
        content = '#EXTM3U\n'
        for channel in channels:
            content += f"#EXTINF:-1 tvg-id=\"{channel['ChannelID']}\",{channel['ChannelName']}\n"
            channel_url = channel['ChannelURL']
            match = re.search(r'.+?://(.+)', channel_url)
            channel_url_prefix = self.config['guide']['channel_url_prefix']
            channel_url = channel_url_prefix + match.group(1)
            content += f"{channel_url}\n"
        return content

    def save_playlist(self, playlist):
        path = self.config['guide']['playlist_path']
        Guide.save_file(path, playlist)
        print(f'Playlist saved to {path}')

    def get_programmes(self, channels):
        programmes = []
        for channel in channels:
            channel_id = channel['ChannelID']
            schedule = self.get_schedule(channel_id)
            programmes_for_schedule = Guide.get_programmes_for_schedule(schedule)
            programmes.extend(programmes_for_schedule)
            print(f'Found {len(programmes_for_schedule)} programmes for channel {channel_id}')
        return programmes

    def get_schedule(self, channel_id):
        params = {'channelId': channel_id}
        response = self.session.get(self.base_url + '/EPG/jsp/liveplay_30/en/getTvodData.jsp', params=params)
        soup = BeautifulSoup(response.text, 'html.parser')
        script = soup.find_all('script', string=re.compile('parent.jsonBackLookStr'))[0].string
        match = re.search(r'parent.jsonBackLookStr\s*=\s*(.+?);', script, re.MULTILINE)
        return json.loads(match.group(1))

    @staticmethod
    def get_programmes_for_schedule(schedule):
        programmes = []
        schedules_by_day = schedule[1]
        for schedule_by_day in schedules_by_day:
            programmes.extend(schedule_by_day)
        return programmes

    @staticmethod
    def get_xmltv(channels, programmes):
        doc = minidom.Document()

        tv_node = doc.createElement('tv')
        tv_node.setAttribute('generator-info-name', 'tv-guide-updater')
        Guide.append_channels(doc, tv_node, channels)
        Guide.append_programmes(doc, tv_node, programmes)
        doc.appendChild(tv_node)

        return doc.toprettyxml(encoding='UTF-8').decode()

    @staticmethod
    def append_channels(doc, tv_node, channels):
        for channel in channels:
            channel_node = doc.createElement('channel')
            channel_node.setAttribute('id', channel['ChannelID'])

            display_name_node = doc.createElement('display-name')
            display_name_node.appendChild(doc.createTextNode(channel['ChannelName']))
            channel_node.appendChild(display_name_node)

            tv_node.appendChild(channel_node)

    @staticmethod
    def append_programmes(doc, tv_node, programmes):
        for programme in programmes:
            programme_node = doc.createElement('programme')
            programme_node.setAttribute('channel', programme['channelId'])
            programme_node.setAttribute('start', f"{programme['beginTimeFormat']} +0800")
            programme_node.setAttribute('stop', f"{programme['endTimeFormat']} +0800")

            title_node = doc.createElement('title')
            title_node.setAttribute('lang', 'zh')
            title_node.appendChild(doc.createTextNode(programme['programName']))
            programme_node.appendChild(title_node)

            tv_node.appendChild(programme_node)

    def save_xmltv(self, xmltv):
        path = self.config['guide']['xmltv_path']
        Guide.save_file(path, xmltv)
        print(f'XMLTV saved to {path}')

    @staticmethod
    def save_file(file, content):
        os.makedirs(os.path.dirname(file), exist_ok=True)
        with open(file, 'w') as f:
            f.write(content)
            f.close()