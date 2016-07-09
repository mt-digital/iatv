'''
iatv.py: Tools for dealing with TV News from the Internet Archive, archive.org
'''

import requests
import warnings

from collections import namedtuple

from pycaption import CaptionConverter, SRTReader
from pycaption.transcript import TranscriptWriter

IATV_BASE_URL = 'https://archive.org/details/tv'
DOWNLOAD_BASE_URL = 'https://archive.org/download/'


def _srt_gen_from_url(base_url, end_time=3660):
    dt = 60
    t0 = 0
    t1 = t0 + dt

    has_next = True
    first = True
    srt = ''

    while has_next:
        url = base_url + '{}/{}'.format(t0, t1)

        print('fetching captions from ' + url)

        if first:
            first = False

            res = requests.get(url)
            res.raise_for_status()

            srt = res.text.replace(u'\ufeff', '')

        else:
            res = requests.get(url)
            res.raise_for_status()

            srt = res.text

        if srt:
            t0 = t1 + 1
            t1 = t1 + dt
            has_next = t1 < end_time

            yield srt.replace('\n\n', ' \n\n')

        else:
            t0 = t1 + 1
            t1 = t1 + dt
            has_next = t1 < end_time

            yield ''


def _make_ts_from_clips(clips_generator):

    c = CaptionConverter()
    c.read('\n'.join((el for el in clips_generator if el)), SRTReader())

    ts = c.write(TranscriptWriter()).replace(u'>>> ', u'>>')

    # import ipdb; ipdb.set_trace()
    return [el.strip()
            for el in ts.replace('\n', ' ').split('>>')
            if el.strip()]


DL_BASE_URL = 'https://archive.org/download/'


def _build_dl_url(datestr, network_name='', show_id_name='', utc_time=''):

    aired_show_id =\
        network_name + '_' + datestr + '_' + utc_time + '_' + show_id_name

    url = DL_BASE_URL + aired_show_id + '/' + aired_show_id + '.cc5.srt?t='

    return url


SHOW_URL_LOOKUP = {
    'oreilly': {
        'show_id_name': 'The_OReilly_Factor',
        'utc_time': '010000',
        'network_name': 'FOXNEWS'
    },
    'redeye': {
        'show_id_name': 'Red_Eye',
        'utc_time': '070000',
        'network_name': 'FOXNEWSW'
    },
    'kelly': {
        'show_id_name': 'The_Kelly_File',
        'utc_time': '020000',
        'network_name': 'FOXNEWSW'
    }
}

# currently explicit at the bottom of file. undecided which to use

# STATION_MAPPINGS = requests.get(
    # 'IATV_BASE_URL?mappings&output=json'
# ).json()[0]


def search_items(query, channel=None, time=None, rows=None, start=None):
    '''
    Search items on the archive.org TV News Archive
    (https://archive.org/details/tv). Use SOLR query format in query.
    Can provide full custom query with the query argument, but leave off
    the "q=". For example

    >>> items = search_items('climate change', channel='FOXNEWSW')

    is equivalent to

    >>> items = search_items('climate change&fc=channel:"FOXNEWSW"')

    and both search using the URL
    ``https://archive.org/details/tv?q=climate change&fc=channel:"FOXNEWSW"``

    Valid ``channel`` values are the keys of STATION_MAPPINGS.

    Arguments:
        query (str): SOLR query with "q=" left off
        channel (str): One of the internet archive channel codes, e.g. FOXNEWSW
        time (str): SOLR-formatted date facet format, YYYY(MM(DD))
        rows (int): number of rows to return
        start (int): row to start at
    Returns:
        (list(dict)) list of show JSON obj with fields
    '''
    url = IATV_BASE_URL + '?q=' + query

    if channel:
        url = url + '&fq=channel:"{}"'.format(channel)
    if time:
        url = url + '&time={}'.format(time)
    if rows:
        url = url + '&rows={}'.format(rows)
    if start:
        url = url + '&start={}'.format(start)

    url = url + '&output=json'

    try:
        return requests.get(url).json()
    except Exception as e:
        print(url)
        raise e


Runtime = namedtuple('Runtime', ['h', 'm', 's'])


class Show:
    '''
    Access an individual Show using the archive.org backend.
    '''
    def __init__(self, identifier):

        try:
            metadata = get_show_metadata(identifier)
            self.metadata = metadata
            self.title = metadata['title'].pop()
            self.identifier = identifier

            _rt = self.metadata['runtime'].pop()
            self.runtime = Runtime(*[int(el) for el in _rt.split(':')])

        except requests.HTTPError:
            warnings.warn(
                'Error loading metadata from archive.org\n'
                'Initializing a new Show with no title or metadata\n'
            )
            self.metadata = None
            self.title = None
            self.identifier = identifier

        self.transcript = ''
        self.last_start_time = None
        self.last_end_time = None

        self.transcript_download_url =\
            DOWNLOAD_BASE_URL + self.identifier + '/' +\
            self.identifier + '.cc5.srt?t='

    def get_transcript(self, start_time=0, end_time=3660):
        '''
        Fetch the transcript for the specified times
        '''
        updated_times = (
            self.last_start_time == start_time and
            self.last_end_time == end_time
        )

        if not self.transcript or updated_times:

            try:
                # XXX not the best, but ok for now. FIXME
                self.transcript = _make_ts_from_clips(
                    _srt_gen_from_url(
                        self.transcript_download_url, end_time=end_time
                    )
                )

            except requests.HTTPError as e:
                warnings.warn('The URL ' + self.transcript_download_url +
                              ' could not be found')

                raise e

        return self.transcript

    def __repr__(self):
        return '<Show>\n\tTitle: {}\n\tIdentifier: {}\n</Show>'.format(
            self.title, self.identifier)

    def __str__(self):
        return '{{\n Title: {}\n Identifier: {}\n}}'.format(
            self.title, self.identifier)


def get_show_metadata(identifier):

    url = 'https://archive.org/details/' + identifier + '?output=json'

    r = requests.get(url)

    return r.json()['metadata']


STATION_MAPPINGS = {
    'ALJAZAM': "Al Jazeera America",
    'BLOOMBERG': "Bloomberg",
    'CNBC': "CNBC",
    'CNN': "CNN",
    'CNNW': "CNN",
    'COM': "Comedy Central",
    'CSPAN': "CSPAN",
    'CSPAN2': "CSPAN",
    'CSPAN3': "CSPAN",
    'CURRENT': "Current",
    'FBC': "FOX Business",
    'FOXNEWS': "FOX News",
    'FOXNEWSW': "FOX News",
    'KBCW': "CW",
    'KCAU': "ABC",
    'KCCI': "Me-TV",
    'KCRG': "ABC",
    'KCSM': "PBS",
    'KDTV': "Univision",
    'KGAN': "CBS",
    'KGO': "ABC",
    'KLAS': "CBS",
    'KMEG': "CBS",
    'KNTV': "NBC",
    'KOLO': "ABC",
    'KPIX': "CBS",
    'KQED': "PBS",
    'KQEH': "PBS",
    'KRCB': "PBS",
    'KSNV': "NBC",
    'KSTS': "Telemundo",
    'KTIV': "NBC",
    'KTNV': "ABC",
    'KTVN': "CBS",
    'KTVU': "FOX",
    'KUSA': "NBC",
    'KVVU': "FOX",
    'KWWL': "NBC",
    'KYW': "CBS",
    'LINKTV': "LINKTV",
    'MSNBC': "MSNBC",
    'MSNBCW': "MSNBC",
    'WABC': "ABC",
    'WBAL': "NBC",
    'WBFF': "FOX",
    'WBZ': "CBS",
    'WCAU': "NBC",
    'WCBS': "CBS",
    'WCPO': "ABC",
    'WCVB': "ABC",
    'WESH': "NBC",
    'WEWS': "ABC",
    'WFDC': "Univision",
    'WFLA': "NBC",
    'WFTS': "ABC",
    'WFTV': "ABC",
    'WFXT': "FOX",
    'WGN': "CW",
    'WHDH': "NBC",
    'WHO': "NBC",
    'WIS': "NBC",
    'WJLA': "ABC",
    'WJW': "FOX",
    'WJZ': "CBS",
    'WKMG': "CBS",
    'WKRC': "CBS",
    'WKYC': "NBC",
    'WLTX': "CBS",
    'WLWT': "NBC",
    'WMAR': "ABC",
    'WMPT': "PBS",
    'WMUR': "ABC",
    'WNBC': "NBC",
    'WNYW': "FOX",
    'WOI': "ABC",
    'WOIO': "CBS",
    'WPLG': "ABC",
    'WPVI': "ABC",
    'WRAL': "CBS",
    'WRC': "NBC",
    'WSPA': "CBS",
    'WTTG': "FOX",
    'WTVD': "ABC",
    'WTVT': "FOX",
    'WTXF': "FOX",
    'WUSA': "CBS",
    'WUVP': "Univision",
    'WYFF': "NBC"
}
