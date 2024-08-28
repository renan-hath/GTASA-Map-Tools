import os
import re
from application.data_entry_types.data_entry import DataEntry

class DataEntryStr(DataEntry):
    IDE_SECTIONS = ['objs', 'tobj', 'anim', 'path', '2dfx', 'txdp', 'cars','hier', 'peds', 'weap']
    IPL_SECTIONS = ['inst', 'cull', 'grge', 'enex', 'pick', 'jump', 'tcyc', 'auzo', 'cars', 'occl', 'path', 'mult']
    DATA_ENTRY_FINALIZER = 'end'
    COMMENT_STARTERS = ('#', ';')

    def __init__(self, content, index, section, file):
        content = content.rstrip('\n')
        super().__init__(content, index, section, file)

    def get_content_elements(self):
        if ',' in self.content or '\t' in self.content:
            temporary_elements = re.split(r'[\t,]\s*', self.content.strip().lower())
            elements = []
            
            for element in temporary_elements:
                if element and not element.startswith(('<')):
                    if ' ' not in element:
                        elements.append(element)
                    else:
                        subelements = re.findall(r'[a-zA-Z_]\w*|\d+\.\d+e[+-]?\d+|\d+\.\d+|\d+|\S+', element)
                        elements.extend([sub.strip() for sub in subelements if sub.strip()])
        else:
            elements = [element.strip().lower() for element in self.content.strip().lower().split() if element.strip()]
        
        return elements

    def formatted_line(self):
        elements = self.get_content_elements()
        formatted_line = ','.join(elements)
        
        return formatted_line

    def update_content_element(self, element, element_index):
        elements = self.get_content_elements()
        elements[element_index] = str(element)
        self._content = ','.join(elements)
    
    def is_ide_section_starter(self):
        return self.formatted_line() in self.IDE_SECTIONS
    
    def is_ipl_section_starter(self):
        return self.formatted_line() in self.IPL_SECTIONS
    
    def is_section_finalizer(self):
        return self.formatted_line() == self.DATA_ENTRY_FINALIZER
    
    def is_comment(self):
        return self.formatted_line().startswith(self.COMMENT_STARTERS)
            
    def is_valid_ide_object(self):
        if (not self.is_comment() and not self.is_ide_section_starter() and
            not self.is_section_finalizer() and self.section in self.IDE_SECTIONS and
            len(self.get_content_elements()) > 1):
            return True
        
    def is_valid_ipl_object(self):
        if (not self.is_comment() and not self.is_ipl_section_starter() and
            not self.is_section_finalizer() and self.section in self.IPL_SECTIONS and
            len(self.get_content_elements()) > 1):
            return True
        
    def is_valid_dat_object(self):
        if (not self.is_comment() and len(self.get_content_elements()) > 1):
            return True