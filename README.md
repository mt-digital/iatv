# iatv

Access archive.org's TV News Archive with Python. For example, to get
the first 100 search results that contain 'climate' or 'change' from
the month of June 2016 on the Fox News Network,

```python
from iatv import Show, search_items

items = search_items('climate change', channel='FOXNEWSW', time='201606', rows=100)
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
