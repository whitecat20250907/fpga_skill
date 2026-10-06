#!/usr/bin/env python3
"""Header-exact inert ISP stubs for lexical elaboration, not ISP verification."""
from pathlib import Path
import re

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
NAMES={'image_correction','ui_BLC','ui_top_demosaic','ui_data128_96','ui_awb',
       'ui_image_cut','ui_gamma','ui_Contrast_adj','ui_Brightness_adj',
       'ui_Saturation_adj','ui_data96_128','sync_fifo_130','pack4_rgb24_to_128'}


def balanced_end(text,start):
    depth=0
    for i in range(start,len(text)):
        if text[i]=='(':depth+=1
        if text[i]==')':
            depth-=1
            if depth==0:return i
    raise ValueError('Unbalanced module header')


def main():
    modules={}
    for path in (ROOT/'fpga/uisrc').rglob('*.v'):
        text=path.read_bytes().decode('latin1')
        text=re.sub(r'/\*.*?\*/','',text,flags=re.S)
        text=re.sub(r'//[^\n]*','',text)
        for match in re.finditer(r'\bmodule\s+(\w+)\b',text):
            name=match.group(1)
            if name not in NAMES:continue
            if name in modules:raise ValueError(f'Duplicate source module {name}')
            pos=match.end()
            while text[pos].isspace():pos+=1
            if text[pos]=='#':
                pos=text.index('(',pos)
                pos=balanced_end(text,pos)+1
            ports_start=text.index('(',pos)
            ports_end=balanced_end(text,ports_start)
            semi=text.index(';',ports_end)
            header=text[match.start():semi+1]
            direction=None;outputs=[]
            for field in text[ports_start+1:ports_end].split(','):
                dirs=re.search(r'\b(input|output|inout)\b',field)
                if dirs:direction=dirs.group(1)
                if direction!='output':continue
                field=re.sub(r'\[[^]]*\]','',field)
                tokens=re.findall(r'\b[A-Za-z_]\w*\b',field)
                outputs.append(tokens[-1])
            modules[name]=header+'\n'+''.join(f"assign {p}=0;\n" for p in outputs)+'endmodule\n'
    if modules.keys()!=NAMES:raise ValueError(f'Missing modules {NAMES-modules.keys()}')
    (HERE/'isp_header_stubs.v').write_text(
        '// Inert header-only stubs; NO ISP/data-path functionality is tested.\n'+
        '\n'.join(modules[name] for name in sorted(modules)),encoding='ascii')
    print('Generated13 exact ISP/packer/FIFO headers; no main sources changed.')


if __name__=='__main__':main()
