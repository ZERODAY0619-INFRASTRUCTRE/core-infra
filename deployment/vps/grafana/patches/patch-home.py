"""Proxy challenge bodies must not be interpreted as valid alert or team arrays."""
REPLACEMENTS = (
    ('s=(a??[]).map(e=>e.name)', 's=(Array.isArray(a)?a:[]).map(e=>e.name)'),
    ('{data:d,isFetching:u,error:h,refetch:m}', '{data:d,isFetching:u,error:responseError,refetch:m}'),
    ('(d??[]).map(n=>', '(Array.isArray(d)?d:[]).map(n=>'),
    ('x=d?.length??0,b=x>0', 'x=Array.isArray(d)?d.length:0,b=x>0'),
    ('return{visibleAlerts:p,count:x', 'let h=responseError??((d!=null&&!Array.isArray(d))||(a!=null&&!Array.isArray(a))?{message:"Invalid alert or team response. Retry after checking the proxy session."}:void 0);return{visibleAlerts:p,count:x'),
)
def patch(source):
    for original, replacement in REPLACEMENTS:
        if source.count(original) != 1:
            raise ValueError(f'Expected exactly one patch target: {original}')
        source = source.replace(original, replacement)
    return source
