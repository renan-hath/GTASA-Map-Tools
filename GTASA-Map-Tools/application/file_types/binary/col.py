from application.data_entry_types.binary.col.col_entry import ColEntry
from application.file_types.objects_file import ObjectsFile

class Col(ObjectsFile):
    COL_SECTION_INDEX = 0
    
    
    COL_TYPE_LENGTH = 4
    FILE_NAME_INTRO_LENGTH = 4
    
    def __init__(self, file_name, file_content):
        super().__init__(file_name, file_content)
        self._section_cols = []
        self.read_file_sections()

    @property
    def section_cols(self):
        return self._section_cols

    @section_cols.setter
    def section_cols(self, col_entry_list):
        if all(isinstance(col_entry, ColEntry) for col_entry in col_entry_list):
            self._section_cols = col_entry_list
        else:
            print(f'Called section_cols setter but {col_entry_list} is not a list of ColEntry.')
            
    def add_to_section_cols(self, col_entry_object):
        if isinstance(col_entry_object, ColEntry):
            self._section_cols.append(col_entry_object)
        else:
            print(f'Called add_to_section_cols but {col_entry_object} is not a ColEntry object.')

    def get_models_names(self):
        models_names = []
        
        for item in self.section_cols:
            models_names.append(item.model)
        
        return models_names
            

    def get_entries_content(self):
        entries = []
        index = 0

        while index < len(self.file_content):
            # Find the first COL occurrence
            col_index = self.file_content.find(b'COL', index)
            
            if col_index == -1:
                break

            # Find the next COL occurrence
            next_col_index = self.file_content.find(b'COL', col_index + 1)
            
            if next_col_index == -1:
                next_col_index = len(self.file_content)  # Fim do arquivo

            # The first COL segment is then stored
            entry_content = self.file_content[col_index:next_col_index]
            
            entries.append(entry_content)

            index = next_col_index

        return entries
    
    def read_file_sections(self):
        col_entries = self.get_entries_content()
        
        for i in range(0, len(col_entries)):
            gta_object = ColEntry(col_entries[i], i, 'collision', self)
            self.add_to_section_cols(gta_object)
                
    def write_file_sections(self):
        file_content = bytearray()
        
        if self.section_cols:
            for col_entry in self.section_cols:
                file_content += col_entry.content
                
        self.file_modified_content = file_content
        return self.file_modified_content