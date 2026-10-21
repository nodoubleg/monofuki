"""Stage the customizer, shared compiler and complete same-run base fonts."""
import hashlib
import json
import re
import shutil
from pathlib import Path
from fetch_tuning_runtime import fetch

ROOT = Path(__file__).resolve().parents[1]


def stage(output, regular, nerd, revision):
    dest = output/'tuning'
    dest.mkdir(exist_ok=True)
    shutil.copy2(ROOT/'website/font-loading.js', output/'font-loading.js')
    for name in ('worker.js','download.js','theme.js'):
        shutil.copy2(ROOT/'website/tuning'/name, dest/name)
        if name == 'download.js':
            path = dest/name
            path.write_text(path.read_text().replace("'tuning/worker.js'", "'tuning/worker.js?v="+revision+"'"))
    shutil.copy2(ROOT/'script_helper/tuning_compiler.py', dest/'tuning_compiler.py')
    runtime = ROOT/'.font-build/tuning-runtime'
    fetch(runtime)
    shutil.copytree(runtime, dest/'runtime', dirs_exist_ok=True)
    (dest/'base').mkdir(exist_ok=True)
    notices = dest/'notices'
    notices.mkdir(exist_ok=True)
    files = []
    def add_file(source, relative):
        target = dest/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source,target)
        files.append({'path':str(relative),'url':str(relative),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
    for family, source_dir in (('Monofuki',regular),('MonofukiNerdFont',nerd)):
        for style in ('Regular','Bold','Italic','BoldItalic'):
            suffix = style.replace('BoldItalic','Bold-Italic') if family == 'Monofuki' else style
            for ext in ('otf','ttf'):
                name = f'{family}-{suffix}.{ext}'
                add_file(source_dir/'tuning-base'/name, Path('base')/name)
    for source_dir in (regular,nerd):
        candidates = set()
        for pattern in ('LICENSE-*','NOTICES-*.md','*provenance.json','*dependencies.json','*additions.json','*overlays.json','*policy.json','*decisions.json','*audit*.md','THIRD-PARTY-NOTICES.txt'):
            candidates.update(source_dir.glob(pattern))
        candidates.update(p for p in (source_dir/'component-notices').rglob('*') if p.is_file())
        for p in sorted(candidates):
            rel = Path('notices')/p.relative_to(source_dir)
            files[:] = [f for f in files if f['path'] != str(rel)]
            add_file(p,rel)
    defaults=json.loads((ROOT/'src/tuning/defaults.json').read_text())
    provenance=json.loads((regular/'tuning-provenance.json').read_text())
    manifest={'revision':revision,'default_configuration_sha256':provenance['configuration_sha256'],
              'compiler_sha256':provenance['compiler_sha256'],'transform_sha256':provenance['transform_sha256'],
              'reference_provenance':provenance['reference_provenance'],'files':files}
    (dest/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    template=(ROOT/'website/tuning/template.html').read_text()
    for key,name in {'GLYPHS':'glyphs.json','ACCENT_COMPONENTS':'accent-components.json','ALTERNATIVES':'g-alternatives.json','EXTRA_ALTERNATIVES':'alternatives.json'}.items():
        template=template.replace('{{'+key+'}}',(ROOT/'src/tuning'/name).read_text())
    template=template.replace('{{APP}}',(ROOT/'website/tuning/app.js').read_text()+'\n'+(ROOT/'website/tuning/preview-editor.js').read_text())
    if re.search(r'\{\{[A-Z_]+\}\}', template):
        raise ValueError('Unresolved customizer template')
    shutil.copy2(ROOT/'website/tuning.css',output/'tuning.css')
    for name in ('tuning/theme.js','tuning/download.js','tuning.css','style.css','font-loading.js'):
        digest = hashlib.sha256((output/name).read_bytes()).hexdigest() if (output/name).exists() else revision
        template = template.replace('src="'+name+'"','src="'+name+'?v='+digest+'"').replace('href="'+name+'"','href="'+name+'?v='+digest+'"')
    (output/'customize.html').write_text(template)
    for name in ('tuning.css','playground.html','playground.js','playground.css'):
        shutil.copy2(ROOT/'website'/name, output/name)
    document = (output/'playground.html').read_text()
    for name in ('tuning/theme.js','style.css','playground.js','playground.css','font-loading.js'):
        digest = hashlib.sha256((output/name).read_bytes()).hexdigest()
        document = document.replace('src="'+name+'"','src="'+name+'?v='+digest+'"').replace('href="'+name+'"','href="'+name+'?v='+digest+'"')
    (output/'playground.html').write_text(document)
    return manifest['default_configuration_sha256']
