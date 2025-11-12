import os
import pathlib
import rss_note_writer as m
print(os.getcwd())
pathlib.Path('debug.txt').write_text('cwd=' + os.getcwd())
print(m.create_default_config(), m.create_default_env())
