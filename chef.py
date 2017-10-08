#!/usr/bin/env python

"""
Sushi Chef for Tahrir Academy:
Videos from https://www.youtube.com/user/tahriracademy/playlists
More from http://en.tahriracademy.net/
"""

# TODO(davidhu): This is basically a copy pasta of the Open Osmosis sushi chef.
# Abstract into a YouTube playlist scraper and make available in Ricecooker
# utils.

from collections import defaultdict
import html
import json
import os
import re
import requests
import tempfile
import time
from urllib.parse import urlparse, parse_qs

from bs4 import BeautifulSoup
import youtube_dl
import pycountry

from le_utils.constants import content_kinds, file_formats, languages
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files, licenses
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter, InvalidatingCacheControlAdapter
from ricecooker.utils.browser import preview_in_browser
from ricecooker.utils.html import download_file, WebDriver, minimize_html_css_js
from ricecooker.utils.zip import create_predictable_zip


sess = requests.Session()
cache = FileCache('.webcache')
forever_adapter = CacheControlAdapter(heuristic=CacheForeverHeuristic(), cache=cache)

#sess.mount('http://', forever_adapter)
#sess.mount('https://', forever_adapter)

ydl = youtube_dl.YoutubeDL({
    'quiet': False, # True
    'no_warnings': True,
    'writesubtitles': True,
    'allsubtitles': True,
})


# SCRAPING YOUTUBE
################################################################################

# Chef settings
################################################################################
DATA_DIR = 'chefdata'
JSON_YOUTUBE_IDS_FILENAME = 'all_video_ids_in_playlists.json'
json_filename = os.path.join(DATA_DIR, JSON_YOUTUBE_IDS_FILENAME)

def download_all_video_infos_from_youtube():
    """
    Returns a list of (youtube_id, title, playlist_id) for all TahrirAcademy videos on youtube.
    """
    if os.path.exists(json_filename):
        with open(json_filename, 'r') as json_file:
            all_video_infos = json.load(json_file)
            return all_video_infos

    youtube_channel_url = 'https://www.youtube.com/user/tahriracademy/playlists?shelf_id=0&view=1&sort=dd'
    print("Fetching YouTube channel and videos metadata --"
            " this may take a few minutes (%s)" % youtube_channel_url)
    info = ydl.extract_info(youtube_channel_url, download=False)

    all_video_infos = []
    for i, playlist in enumerate(info['entries']):
        title = playlist['title']
        youtube_url = playlist['webpage_url']
        print("  Downloading playlist %s (%s)" % (title, youtube_url))
        # playlist_topic = nodes.TopicNode(source_id=playlist['id'], title=title)
        for j, video in enumerate(playlist['entries']):
            # print('found video  youtube_id=', j, video['id'])
            all_video_infos.append( (video['id'], title, playlist['id']) )
    # print('all_video_infos=', all_video_infos)

    # save json cache
    data_out = []
    for youtube_id, title, playlist_id in all_video_infos:
        data_out.append(
            dict(
                youtube_id=youtube_id,
                title=title,
                playlist_id=playlist_id,
            )
        )
    with open(json_filename, 'wb') as json_file:
        json_string = json.dumps(data_out, ensure_ascii=False, indent=4).encode('utf8')
        json_file.write(json_string)

    return all_video_infos


class TahrirAcademyChef(SushiChef):
    """
    The chef class that takes care of uploading channel to the content curation server.

    We'll call its `main()` method from the command line script.
    """
    channel_info = {
        'CHANNEL_SOURCE_DOMAIN': "http://tahriracademy.org/",
        'CHANNEL_SOURCE_ID': "tahrir-academy",
        'CHANNEL_TITLE': "Tahrir Academy",
        'CHANNEL_THUMBNAIL': "https://yt3.ggpht.com/-t2RMfv5dBMM/AAAAAAAAAAI/AAAAAAAAAAA/DL3ELFokTGY/s288-c-k-no-mo-rj-c0xffffff/photo.jpg",
        'CHANNEL_DESCRIPTION': "One of the largest Arabic language content sources of locally produced educational videos. Aligned to the Egyptian curriculum as well as that of various other countries across the Middle East and North African region on a case-by-case basis for individual sets of content.",
    }

    def construct_channel(self, **kwargs):
        """
        Create ChannelNode and build topic tree.
        """
        # create channel
        channel_info = self.channel_info
        channel = nodes.ChannelNode(
            source_domain = channel_info['CHANNEL_SOURCE_DOMAIN'],
            source_id = channel_info['CHANNEL_SOURCE_ID'],
            title = channel_info['CHANNEL_TITLE'],
            thumbnail = channel_info.get('CHANNEL_THUMBNAIL'),
            description = channel_info.get('CHANNEL_DESCRIPTION'),
            language = "ar",
        )
        return channel


def fetch_video(video):
    youtube_id = video['id']
    title = video['title']
    description = video['description']
    youtube_url = video['webpage_url']

    print("    Fetching video data: %s (%s)" % (title, youtube_url))

    video_node = nodes.VideoNode(
        source_id=youtube_id,
        title=truncate_metadata(title),
        license=licenses.CC_BY_NC_NDLicense(
            copyright_holder='Tahrir Academy (tahriracademy.org)'),
        description=truncate_description(description),
        derive_thumbnail=True,
        language="ar",
        files=[files.YouTubeVideoFile(youtube_id=youtube_id)],
    )

    return video_node


DESCRIPTION_RE = re.compile('Subscribe - .*$')

def truncate_description(description):
    # Return all the lines up to one before the first line that starts with "http"
    lines = description.splitlines()
    cut_index = next((i for i, line in enumerate(lines) if line.startswith('http')), len(lines))
    return '\n'.join(lines[:max(cut_index - 1, 1)])


def truncate_metadata(data_string):
    MAX_CHARS = 190
    if len(data_string) > MAX_CHARS:
        data_string = data_string[:190] + " ..."
    return data_string


if __name__ == '__main__':
    """
    This code will run when the sushi chef is called from the command line.
    """
    chef = TahrirAcademyChef()
    chef.main()
