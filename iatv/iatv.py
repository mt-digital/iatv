'''
iatv.py: Tools for dealing with TV News from the Internet Archive, archive.org
'''
import glob
import json
import os
import re
import requests
import unicodedata
import warnings

from collections import namedtuple
from dateutil.parser import parse

from pycaption import CaptionConverter, SRTReader, SRTWriter
from pycaption.transcript import TranscriptWriter

from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer as Summarizer
from sumy.nlp.stemmers import Stemmer
from sumy.utils import get_stop_words

IATV_BASE_URL = 'https://archive.org/details/tv'
DOWNLOAD_BASE_URL = 'https://archive.org/download/'

LANGUAGE = 'english'

SENTENCES_COUNT = 10


def summarize_standard_dir(directory, n_sentences):
    '''
    If it doesn't already exist, create summary.txt in the unique identifier
    data directory, i.e. {directory}/{identifier}/summary.txt to go alongside
    {directory}/{identifier}/transcript.txt and
    {directory}/{identifier}/metadata.json.
    '''
    for d in glob.glob(os.path.join(directory, '*')):

        if os.path.isdir(d):
            summary_path = os.path.join(d, 'summary.txt')
        else:
            raise RuntimeError(
                'There should only be directories in ' + directory
            )

        if not os.path.exists(summary_path):

            try:
                transcript_path = os.path.join(d, 'transcript.txt')
                text = open(transcript_path).read()
                open(summary_path, 'w+').write(
                    summarize(text, n_sentences)
                )

            except Exception as e:

                print('Error writing to ' + summary_path)
                print(e.message)
                pass


def summarize(text, n_sentences, sep='\n'):
    '''
    Args:
        text (str or file): text itself or file in memory of text
        n_sentences (int): number of sentences to include in summary

    Kwargs:
        sep (str): separator to join summary sentences

    Returns:
        (str) n_sentences-long, automatically-produced summary of text
    '''

    if isinstance(text, str):
        parser = PlaintextParser.from_string(text, Tokenizer(LANGUAGE))
    elif isinstance(text, file):
        parser = PlaintextParser.from_file(text, Tokenizer(LANGUAGE))
    else:
        raise TypeError('text must be either str or file')

    stemmer = Stemmer(LANGUAGE)

    summarizer = Summarizer(stemmer)
    summarizer.stop_words = get_stop_words(LANGUAGE)

    return '\n'.join(str(s) for s in summarizer(parser.document, n_sentences))


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

    res = requests.get(url)
    try:
        return res.json()
    except Exception as e:
        try:

            # a hack for msnbc october 2016 data
            data = requests.get(url).text.replace(',\n,', ',\n')
            return json.loads(data)

        except Exception as e2:
            data = requests.get(url).data
            raise e2


Runtime = namedtuple('Runtime', ['h', 'm', 's'])


class Show:
    '''
    Access an individual Show using the archive.org backend.

    Example:

    >>> from iatv import search_items, Show
    >>> shows = [item for item
                 in search_items('climate change', channel='FOXNEWSW',
                                 time='201607', rows=1000)
                 if 'commercial' not in item
                ]
    >>> s = Show(shows.pop()['identifier'])
    >>> tr = s.get_transcript(verbose=False)  # download captions to this object in memory
    >>> open('transcript-out.txt', 'w').write('\n\n'.join(tr).encode('utf-8'))
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

        self.srt = ''
        self.srt_fname = ''
        self.transcript = ''
        self.last_start_time = None
        self.last_end_time = None

        self.transcript_download_url =\
            DOWNLOAD_BASE_URL + self.identifier + '/' +\
            self.identifier + '.cc5.srt'

    def download_video(self, start_time=0, stop_time=60, download_path=None):

        if not download_path:
            download_path = self.identifier + '_{}_{}.mp4'.format(
                    start_time, stop_time
                )

        url = DOWNLOAD_BASE_URL + self.identifier + '/' +\
            self.identifier + '.mp4?t=' + str(start_time) + '/' +\
            str(stop_time) + '&exact=1&ignore=x.mp4'

        res = requests.get(url)

        with open(download_path, 'wb') as handle:
            handle.write(res.content)

    def get_transcript(self, start_time=0, end_time=None, verbose=True):
        '''
        Fetch the transcript for the specified times
        '''
        updated_times = (
            self.last_start_time == start_time and
            self.last_end_time == end_time
        )

        if not self.transcript or updated_times:

            if not end_time:
                try:
                    h, m, s = self.metadata['runtime'].pop().split(':')
                    end_time = (3600 * int(h)) + (60 * int(m)) + int(s)
                except IndexError:
                    try:
                        end_time = timedelta_from_title(self.title)
                    except:
                        end_time = 3600

            try:
                self.srt = '\n\n'.join(
                    _srt_gen_from_url(
                        self.transcript_download_url,
                        end_time=end_time,
                        verbose=verbose
                    )
                )

                self.srt_fname = self.transcript_download_url.replace(
                    'https://archive.org/download/', ''
                ).split('?t=')[0].split('/')[-1]

                # XXX not the best, but ok for now. FIXME
                self.transcript = _make_ts_from_srt(self.srt)

            except Exception as e:
                warnings.warn(
                    'Failed to recover transcript from URL ' +
                    self.transcript_download_url + '\n\n' + e.message
                )

        return self.transcript

    def __repr__(self):
        return '<Show>\n\tTitle: {}\n\tIdentifier: {}\n</Show>'.format(
            self.title, self.identifier)

    def __str__(self):
        return '{{\n Title: {}\n Identifier: {}\n}}'.format(
            self.title, self.identifier)


def download_all_transcripts(show_specs, base_directory=None, verbose=True):
    '''
    Download all transcripts for shows corresponding to their
    specification in each element of show_specs. Each show_spec should
    be a dictionary in the list returned from ``search_items``.

    Example:

    >>> items = search_items('I', channel='FOXNEWSW', time='201607', rows=100000)
    >>> shows = [item in items if 'commercial' not in item]
    >>> download_all_transcripts(shows, base_directory='July2016')


    Arguments:
        show_specs (list(dict)): list of specifications returned by
            search_items function
        base_directory (str): directory where downloads should be put
    '''

    if not base_directory:
        base_directory = 'default-downloads'

    if not os.path.isdir(base_directory):
        os.makedirs(base_directory)

    for spec in show_specs:

        iden = spec['identifier']
        show = Show(iden)
        write_dir = os.path.join(base_directory, iden)

        if not os.path.exists(os.path.join(write_dir, 'transcript.txt')):

            if os.path.isdir(write_dir):
                os.removedirs(write_dir)

            os.mkdir(write_dir)

            ts = show.get_transcript(verbose=verbose)
            ts_file_path = os.path.join(write_dir, 'transcript.txt')
            open(ts_file_path, 'w').write('\n\n'.join(ts).encode('utf-8'))

            md = show.metadata
            md.update(spec)
            md_file_path = os.path.join(write_dir, 'metadata.json')
            open(md_file_path, 'w').write(json.dumps(md).encode('utf-8'))

            srt_file_path = os.path.join(write_dir, show.srt_fname)
            open(srt_file_path, 'w').write(show.srt.encode('utf-8'))


TIMES_PATT = re.compile(
    r'[1]{0,1}[0-9]:[0-9]{2}[a,p]m-[1]{0,1}[0-9]:[0-9]{2}[a,p]m'
)


def timedelta_from_title(title):

    st, et = (
        parse(time_str)
        for time_str in TIMES_PATT.findall(title).pop().split('-')
    )

    return (et - st).seconds


def get_show_metadata(identifier):

    url = 'https://archive.org/details/' + identifier

    r = requests.get(url, params={'output': 'json'},
                     headers={'Content-type': 'application/json'})

    return r.json()['metadata']


def _srt_gen_from_url(base_url, end_time=3660, verbose=True):

    dt = 60
    t0 = 0
    t1 = t0 + dt

    has_next = True
    first = True
    srt = ''

    last_end = 0.0
    while has_next:

        if verbose:
            print('fetching captions from ' +
                  base_url + '?t={}/{}'.format(t0, t1))

        if first:
            first = False
            res = requests.get(base_url, params={'t': '{}/{}'.format(t0, t1)})
            res.raise_for_status()
            print(res.url)

            srt = res.text.replace(u'\ufeff', '')

        else:
            res = requests.get(base_url, params={'t': '{}/{}'.format(t0, t1)})

            res.raise_for_status()
            print(res.url)

            srt = res.text

        t0 = t1 + 1
        t1 = t1 + dt
        has_next = t1 <= end_time

        if srt:

            cc = CaptionConverter()
            cc.read(srt, SRTReader())
            captions = cc.captions.get_captions(lang='en-US')

            if first:
                last_end = captions[-1].end

            else:
                for caption in captions:
                    caption.start += last_end
                    caption.end += last_end

                last_end = captions[-1].end

            srt = cc.write(SRTWriter())

            yield srt.replace('\n\n', ' \n\n')

        else:
            yield ''


def _make_ts_from_srt(srt):

    c = CaptionConverter()

    srt = re.sub('$', ' ', srt).replace('\n\n', ' \n\n')

    srt = unicodedata.normalize('NFC', srt)

    srt = ''.join(i for i in srt
                  if unicodedata.category(i)[0] != 'C' or i == '\n')

    c.read(srt, SRTReader())

    ts = c.write(TranscriptWriter()).replace(u'>>> ', u'>>').replace('\n', ' ')

    return ts.split('>>')


DL_BASE_URL = 'https://archive.org/download/'


def _build_dl_url(datestr, network_name='', show_id_name='', utc_time=''):

    aired_show_id =\
        network_name + '_' + datestr + '_' + utc_time + '_' + show_id_name

    url = DL_BASE_URL + aired_show_id + '/' + aired_show_id + '.cc5.srt?t='

    return url


STATION_MAPPINGS = {
    'ALJAZAM': 'Al Jazeera America',
    'BLOOMBERG': 'Bloomberg',
    'CNBC': 'CNBC',
    'CNN': 'CNN',
    'CNNW': 'CNN',
    'COM': 'Comedy Central',
    'CSPAN': 'CSPAN',
    'CSPAN2': 'CSPAN',
    'CSPAN3': 'CSPAN',
    'CURRENT': 'Current',
    'FBC': 'FOX Business',
    'FOXNEWS': 'FOX News',
    'FOXNEWSW': 'FOX News',
    'KBCW': 'CW',
    'KCAU': 'ABC',
    'KCCI': 'Me-TV',
    'KCRG': 'ABC',
    'KCSM': 'PBS',
    'KDTV': 'Univision',
    'KGAN': 'CBS',
    'KGO': 'ABC',
    'KLAS': 'CBS',
    'KMEG': 'CBS',
    'KNTV': 'NBC',
    'KOLO': 'ABC',
    'KPIX': 'CBS',
    'KQED': 'PBS',
    'KQEH': 'PBS',
    'KRCB': 'PBS',
    'KSNV': 'NBC',
    'KSTS': 'Telemundo',
    'KTIV': 'NBC',
    'KTNV': 'ABC',
    'KTVN': 'CBS',
    'KTVU': 'FOX',
    'KUSA': 'NBC',
    'KVVU': 'FOX',
    'KWWL': 'NBC',
    'KYW': 'CBS',
    'LINKTV': 'LINKTV',
    'MSNBC': 'MSNBC',
    'MSNBCW': 'MSNBC',
    'WABC': 'ABC',
    'WBAL': 'NBC',
    'WBFF': 'FOX',
    'WBZ': 'CBS',
    'WCAU': 'NBC',
    'WCBS': 'CBS',
    'WCPO': 'ABC',
    'WCVB': 'ABC',
    'WESH': 'NBC',
    'WEWS': 'ABC',
    'WFDC': 'Univision',
    'WFLA': 'NBC',
    'WFTS': 'ABC',
    'WFTV': 'ABC',
    'WFXT': 'FOX',
    'WGN': 'CW',
    'WHDH': 'NBC',
    'WHO': 'NBC',
    'WIS': 'NBC',
    'WJLA': 'ABC',
    'WJW': 'FOX',
    'WJZ': 'CBS',
    'WKMG': 'CBS',
    'WKRC': 'CBS',
    'WKYC': 'NBC',
    'WLTX': 'CBS',
    'WLWT': 'NBC',
    'WMAR': 'ABC',
    'WMPT': 'PBS',
    'WMUR': 'ABC',
    'WNBC': 'NBC',
    'WNYW': 'FOX',
    'WOI': 'ABC',
    'WOIO': 'CBS',
    'WPLG': 'ABC',
    'WPVI': 'ABC',
    'WRAL': 'CBS',
    'WRC': 'NBC',
    'WSPA': 'CBS',
    'WTTG': 'FOX',
    'WTVD': 'ABC',
    'WTVT': 'FOX',
    'WTXF': 'FOX',
    'WUSA': 'CBS',
    'WUVP': 'Univision',
    'WYFF': 'NBC'
}
