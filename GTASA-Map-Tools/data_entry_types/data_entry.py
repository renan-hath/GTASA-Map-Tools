class DataEntry:
    COMMENT_STARTER = '#'
    IDE_SECTION_STARTERS = ['objs', 'tobj', 'anim']
    IPL_SECTION_STARTERS = ['inst', 'cull', 'grge', 'enex', 'pick', 'jump', 'tcyc', 'auzo', 'cars', 'occl']
    IDE_SECTION_FINALIZERS = ['end']
    IPL_SECTION_FINALIZERS = ['end']

    def __init__(self, line):
        self._line = line

    @property
    def line(self):
        return self._line
    
    @line.setter
    def line(self, line):
        self._line = line

    def get_line_elements(self):
        elements = [element.strip().lower() for element in self.line.split(',')]
        
        return elements

    def update_line_element(self, element, element_index):
        elements = self.get_line_elements()
        elements[element_index] = str(element)
        self._line = ','.join(elements)

    def formated_line(self):
        elements = self.get_line_elements()
        formated_line = ','.join(elements)
        
        return formated_line
    
    def is_comment(self):
        return self.formated_line().startswith(self.COMMENT_STARTER)
    
    def is_section_starter(self, file_extension):
        if (file_extension == 'ide' and self.formated_line() in self.IDE_SECTION_STARTERS or
            file_extension == 'ipl' and self.formated_line() in self.IPL_SECTION_STARTERS):
                return True
            
    def is_section_finalizer(self, file_extension):
        if (file_extension == 'ide' and self.formated_line() in self.IDE_SECTION_FINALIZERS or
            file_extension == 'ipl' and self.formated_line() in self.IPL_SECTION_FINALIZERS):
                return True