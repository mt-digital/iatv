import responses
import requests as r

from iatv.iatv import Show, DOWNLOAD_BASE_URL, IATV_BASE_URL


@responses.activate
def test_srt_building():
    '''
    SRT should have contiguous, continuous timings; each response from IATV starts at 00:00:00
    '''
    test_show_id = 'Test_Show'

    metadata_url = 'https://archive.org/details/' + \
        test_show_id + '?output=json'

    url1 = DOWNLOAD_BASE_URL + test_show_id + '/' +\
        test_show_id + '.cc5.srt?t=0/60'
    url2 = DOWNLOAD_BASE_URL + test_show_id + '/' +\
        test_show_id + '.cc5.srt?t=61/120'

    with responses.RequestsMock() as rsps:

        rsps.add(responses.GET,
                 'https://archive.org/details/Test_Show?output=json',
                 json={'metadata':
                       {'title': ['test show'],
                        'runtime': ['01:00:00']}
                       },
                 content_type='application/json',
                 status=200,
                 match_querystring=True)

        srt1 = '''1
00:00:00,000 --> 00:00:10,312
This is an example SRT file,
which, while extremely short,
is still a valid SRT file.
'''

        srt2 = '''1
00:00:00,000 --> 00:00:10,312
This is an example SRT file,
which, while extremely short,
is still a valid SRT file.
'''
        rsps.add(responses.GET, url1, body=srt1,
                 match_querystring=True)

        rsps.add(responses.GET, url2, body=srt2,
                 match_querystring=True)

        s = Show(test_show_id)

        s.get_transcript(end_time=120)

        assert s.metadata == {'title': [],
                              'runtime': []}, s.metadata


@responses.activate
def test_should_work():
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, 'http://yo.io', json={'url': 'http://yo.io'}, content_type='application/json', status=200)

        rsps.add(responses.GET, DOWNLOAD_BASE_URL + 'test/test.cc5.srt?t=10/20', body='00:00:00 YO! 01:00:00',
                 content_type='text/plain',
                 match_querystring=True)

        res = r.get('http://yo.io')

        res2 = r.get(DOWNLOAD_BASE_URL + 'test/test.cc5.srt', params={'t': '10/20'})

        assert res.json() == {'url': 'http://yo.io'}
        assert res2.text == '00:00:00 YO! 01:00:00', res2.text
