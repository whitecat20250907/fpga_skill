"""Select the CSR wire contract independently from the visual layout."""
def csr_mode(mipi):
    profile=mipi.get('profile','legacy')
    if profile not in ('legacy','theater'):
        raise ValueError('Unknown MIPI layout')
    if not mipi.get('csr_enabled',False):
        if profile=='theater':raise ValueError('Theater requires UI11 CSR')
        return 0
    protocol=mipi.get('csr_protocol','ui11' if profile=='theater' else 'ui10')
    if protocol not in ('ui10','ui11'):raise ValueError('Unknown MIPI CSR protocol')
    if profile=='theater' and protocol!='ui11':raise ValueError('Theater requires UI11 CSR')
    return 2 if protocol=='ui11' else 1
