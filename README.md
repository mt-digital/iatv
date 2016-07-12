# iatv

Access archive.org's TV News Archive with Python. For example, to get
the first 100 search results that contain 'climate' or 'change' from
the month of July 2016 on the Fox News Network,

```python
from iatv import Show, search_items

items = search_items('climate change', channel='FOXNEWSW', time='201607', rows=100)
# filter out commercials
shows = [item for item in items if 'commercial' not in item]
```

Then let's download the whole transcript of the first record in
`shows`. We won't just get the raw captions.

```python
show = Show(shows[0].identifier)
trans = show.get_transcript()
```

`iatv` will print status updates to screen as the transcript is built.
Closed captions have to be fetched in roughly 60-second intervals,
apparently for legal reasons. However we can still build full
transcripts from this access.

`trans` will be a list of strings, with each unnamed person's turn
talking being a string in the list. We can zip these together and
build a reasonable transcript like so

```python
fulltext = u'\n\n'.join(trans).encode('utf-8')
open(show.identifier + '.txt', 'w').write(fulltext)
```


## More examples/recipes

### download all transcripts from Fox News for a series of days

Note that if you are downloading the same transcripts often, for example for
iteratively developing a processing pipeline, the best practice is to
cache the results somehow. Here we'll show how to save them to file.

This is not necessarily the best or most responsible way to do this.

```python
import os
from iatv import search_items, Show

days = ['01', '02', '03']
times = ['201607' + el for el in days]

items = [item
         for time in times
         for item in
            search_items('I', channel='FOXNEWSW', time=time, rows=1000)]

shows = [item in items if 'commercial' not in item]

for show_spec in shows:
    iden = show_spec['identifier']
    show = Show(iden)
    os.mkdir(iden)

    ts = show.get_transcript()
    ts_file_path = os.path.join(iden, 'transcript.txt')
    open(ts_file_path, 'w').write('\n\n'.join(ts).encode('utf-8'))

    md = show.metadata
    md_file_path = os.path.join(iden, 'metadata.json')
    open(md_file_path, 'w').write(json.dumps(md).encode('utf-8'))
```


This is wrapped up in a function called `download_all_transcripts` that takes
a list of show specifications (search results from `search_items`) and
downloads all their transcripts and metadata to directories of the form
`<base_directory>/<show_identifier>/{transcript.txt,metadata.json}`.

For example, to download all transcripts from July 2016, run

```python
items = search_items('I', channel='FOXNEWSW', time='201607', rows=100000)
shows = [item in items if 'commercial' not in item]

download_all_transcripts(shows, base_directory='July2016')
```

Note that if the directory for an identifier already exists, it will be
skipped to avoid re-downloading existing data. This will report on every URL it
downloads from. To turn off this reporting, add the kwarg `verbose=False` to
the `download_all_transcripts` call.

### Summarize all transcripts downloaded above

Now let's make summaries of all of these downloaded files and save these
summaries to the same identifier-specific directories. So using the same
variables as above,

```python
base_directory = 'July2016'
n_sentences = 12

# run this then open July2016/FOXNEWSW_20160701_000000_The_OReilly_Factor/summary.txt
summarize_standard_dir(base_directory, n_sentences)
```
