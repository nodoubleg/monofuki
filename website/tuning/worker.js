'use strict';
let runtime;
const revision=new URL(self.location).searchParams.get('v')||'dev';
const source = async url => {const r=await fetch(url+(url.includes('?')?'&':'?')+'v='+revision);if(!r.ok)throw Error(`Could not load ${url} (${r.status}).`);return r;};
async function initialize(){
  importScripts('runtime/pyodide.js');
  const py=await loadPyodide({indexURL:new URL('runtime/',self.location).href});
  await py.loadPackage(['fonttools','brotli']);
  py.FS.writeFile('/tuning_compiler.py',await (await source('tuning_compiler.py')).text());
  py.runPython('import sys; sys.path.insert(0, "/")');
  const manifest=await (await source('manifest.json')).json();
  py.FS.mkdirTree('/base');py.FS.mkdirTree('/notices');
  for(const file of manifest.files.filter(file=>!file.path.startsWith('base/'))){
    const data=new Uint8Array(await (await source(file.url)).arrayBuffer());
    const digest=[...new Uint8Array(await crypto.subtle.digest('SHA-256',data))].map(x=>x.toString(16).padStart(2,'0')).join('');
    if(digest!==file.sha256)throw Error('Build input checksum mismatch. Reload this page.');
    py.FS.mkdirTree('/'+file.path.split('/').slice(0,-1).join('/'));
    py.FS.writeFile('/'+file.path,data);
  }
  return {py,manifest};
}
onmessage=async({data})=>{
  if(data.type!=='build')return;
  try{
    postMessage({type:'progress',text:'Loading the local font compiler…'});
    runtime ||= initialize().catch(error=>{runtime=null;throw error;});
    const {py,manifest}=await runtime;
    const family=data.payload.family==='nerd'?'MonofukiNerdFont':'Monofuki';
    for(const file of manifest.files.filter(file=>file.path.startsWith('base/'+family+'-'))){
      if(py.FS.analyzePath('/'+file.path).exists)continue;
      const bytes=new Uint8Array(await (await source(file.url)).arrayBuffer());
      const digest=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(x=>x.toString(16).padStart(2,'0')).join('');
      if(digest!==file.sha256)throw Error('Base font checksum mismatch. Reload this page.');
      py.FS.writeFile('/'+file.path,bytes);
    }
    py.globals.set('request_json',JSON.stringify(data.payload));
    py.globals.set('manifest_json',JSON.stringify(manifest));
    py.runPython(`import json, pathlib, io, zipfile, hashlib
from tuning_compiler import compile_font, config_identity, to_woff2
request = json.loads(request_json)
manifest = json.loads(manifest_json)
settings = request['settings']
identity, configuration = config_identity(settings)
is_default = identity == manifest['default_configuration_sha256']
bundle = io.BytesIO()
archive = zipfile.ZipFile(bundle, 'w', zipfile.ZIP_DEFLATED)
reports = {}
webfonts = {}
def add_file(name, data):
    info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(info, data)
for item in pathlib.Path('/notices').rglob('*'):
    if item.is_file(): add_file(str(item.relative_to('/notices')), item.read_bytes())
`);
    py.globals.set('family',family);
    const styles=['Regular','Bold','Italic','BoldItalic'];
    for(const [index,style] of styles.entries()){
      const label=style.replace('BoldItalic','Bold Italic');
      py.globals.set('style',style);
      for(const ext of ['otf','ttf']){
        postMessage({type:'progress',text:`Building ${label} ${ext.toUpperCase()} · style ${index+1}/4…`});
        py.globals.set('ext',ext);
        py.runPython(`suffix = style.replace('BoldItalic', 'Bold-Italic') if family == 'Monofuki' else style
name = f'{family}-{suffix}.{ext}'
data, report = compile_font(pathlib.Path('/base', name).read_bytes(), request['styles'][style], settings, style, default=is_default)
output_name = f'{family}-{identity[:8]}-{suffix}.{ext}'
add_file(output_name, data)
report['output_sha256'] = hashlib.sha256(data).hexdigest()
reports[output_name] = report
`);
        if(ext==='otf'){
          postMessage({type:'progress',text:`Compressing ${label} webfont · style ${index+1}/4…`});
          py.runPython(`webfonts[style] = to_woff2(data)
add_file(f'{family}-{identity[:8]}-{suffix}.woff2', webfonts[style])`);
        }
      }
      const value=py.runPython('webfonts[style]');
      let font;try{font=value.toJs();}finally{value.destroy();}
      postMessage({type:'font',style,bytes:font},[font.buffer]);
    }
    const result=py.runPython(`add_file('tuning-settings.json', json.dumps(settings, ensure_ascii=False, indent=2).encode())
add_file('tuning-provenance.json', json.dumps({'configuration_sha256':identity,'source_revision':manifest['revision'],'compiler_sha256':manifest['compiler_sha256'],'transform_sha256':manifest['transform_sha256'],'reference_provenance':manifest['reference_provenance'],'files':reports}, indent=2).encode())
add_file('README.txt', b'Monofuki custom build: four real styles, OTF/TTF/WOFF2.\\nChoose one installable format per family. No installation is performed by this page.\\nContextual ink placement uses OpenType kern; applications may disable it. Advances stay 575.\\nThe source settings and exact component notices accompany this build.\\n')
archive.close()
bundle.getvalue()` );
    let bytes;try{bytes=result.toJs();}finally{result.destroy();}
    postMessage({type:'complete',bytes,identity:py.globals.get('identity'),family},[bytes.buffer]);
  }catch(error){postMessage({type:'error',text:error.message||String(error)});}
};
