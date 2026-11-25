"""Proxy challenge responses must fail before Grafana stores API state."""
from pathlib import Path

def patch(source):
    validator = Path(__file__).with_name('validate-api-response.js').read_text()
    replacements = (
        ('d=e.responseType??(Z(i)?"json":void 0);return{status:a,statusText:r,ok:n,data:await ee(t,d),',
         'd=e.responseType??(Z(i)?"json":void 0),validatedData=await ee(t,d);(' + validator + ')(e,t,validatedData);return{status:a,statusText:r,ok:n,data:validatedData,'),
        ('()=>e.map(e=>({label:e.name,description:e.role,value:e}))',
         '()=>(Array.isArray(e)?e:[]).map(e=>({label:e.name,description:e.role,value:e}))'),
        ('},[a]),n?.length<=1)return e;', '},[a]),!Array.isArray(n)||n.length<=1)return e;'),
    )
    for original, replacement in replacements:
        if source.count(original) != 1:
            raise ValueError(f'Expected exactly one patch target: {original}')
        source = source.replace(original, replacement)
    return source
