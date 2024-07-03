class DataEntry:
    COMMENT_STARTER = '#'
    IDE_SECTIONS = ['objs', 'tobj', 'anim', 'path', '2dfx', 'txdp', 'hier']
    IPL_SECTIONS = ['inst', 'cull', 'grge', 'enex', 'pick', 'jump', 'tcyc', 'auzo', 'cars', 'occl', 'path', 'mult']
    IDE_SECTION_FINALIZERS = ['end']
    IPL_SECTION_FINALIZERS = ['end']

    def __init__(self, line, section, file_type):
        self._line = line
        self._section = section
        self._file_type = file_type

    @property
    def line(self):
        return self._line
    
    @line.setter
    def line(self, line):
        self._line = line
        
    @property
    def section(self):
        return self._section
    
    @section.setter
    def section(self, section):
        self._section = section
        
    @property
    def file_type(self):
        return self._file_type
    
    @file_type.setter
    def file_type(self, file_type):
        self._file_type = file_type

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
    
    def is_section_starter(self):
        if (self.file_type == 'ide' and self.formated_line() in self.IDE_SECTIONS or
            self.file_type == 'ipl' and self.formated_line() in self.IPL_SECTIONS):
                return True
            
    def is_section_finalizer(self):
        if (self.file_type == 'ide' and self.formated_line() in self.IDE_SECTION_FINALIZERS or
            self.file_type == 'ipl' and self.formated_line() in self.IPL_SECTION_FINALIZERS):
                return True
            
    def is_object_in_valid_session(self):
        if (self.file_type == 'ide' and self.section in self.IDE_SECTIONS and self.line != self.section or
            self.file_type == 'ipl' and self.section in self.IPL_SECTIONS and self.line != self.section):
                return True