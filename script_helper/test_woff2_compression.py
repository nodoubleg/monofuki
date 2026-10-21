#!/usr/bin/env python3
"""Verify the faster WOFF2 encoder changes compression only, including errors."""
import io
import json
import time
from pathlib import Path
from unittest.mock import patch
from fontTools.ttLib import TTFont, woff2
from tuning_compiler import to_woff2
ROOT=Path(__file__).resolve().parents[1]

def table_bytes(data):
    font=TTFont(io.BytesIO(data))
    return {tag:font.reader[tag]for tag in font.reader.keys()}

def main():
    original=woff2.brotli
    reports=[]
    for source in sorted((ROOT/'export').glob('Monofuki-*.otf'))+sorted((ROOT/'export').glob('MonofukiNerdFont-*.otf'))+sorted((ROOT/'export').glob('Monofuki-*-hinted.ttf')):
        data=source.read_bytes();start=time.perf_counter();fast=to_woff2(data);elapsed=time.perf_counter()-start
        # Quality zero is a fast independent compression reference for every
        # format/style; compare maximum quality on both CFF and hinted glyf.
        q=11 if source.name in ('Monofuki-Italic.otf','Monofuki-Regular-hinted.ttf') else 0
        reference=to_woff2(data,quality=q)
        assert table_bytes(fast)==table_bytes(reference),source.name
        assert woff2.brotli is original
        reports.append({'file':source.name,'seconds':round(elapsed,3),'bytes':len(fast),'reference_quality':q,'all_decoded_tables_equal':True})
        print('PASS',source.name,'all decoded WOFF2 tables identical; quality9',round(elapsed,3),'seconds',flush=True)
    with patch.object(TTFont,'save',side_effect=RuntimeError('test writer failure')):
        try:to_woff2(data)
        except RuntimeError:pass
        else:raise AssertionError('Expected injected failure')
    assert woff2.brotli is original
    output=ROOT/'.font-build/woff2-compression-checks.json';output.write_text(json.dumps(reports,indent=2)+'\n')
    print('PASS',len(reports),'font roundtrips and encoder restoration on failure')
if __name__=='__main__':main()
