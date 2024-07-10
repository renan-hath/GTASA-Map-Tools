import os
from abc import ABC, abstractmethod

class ObjectsFile(ABC):
    def __init__(self, file_name, file_content):
        self._file_name = file_name
        self._file_type = os.path.splitext(file_name)[1][1:].lower()
        self._file_content = file_content
        self._file_modified_content = file_content

    @property
    def file_name(self):
        return self._file_name

    @file_name.setter
    def file_name(self, file_name):
        self._file_name = file_name

    @property
    def file_type(self):
        return self._file_type

    @file_type.setter
    def file_type(self, file_type):
        self._file_type = file_type
        
    @property
    def file_content(self):
        return self._file_content

    @file_content.setter
    def file_content(self, file_content):
        self._file_content = file_content
        
    @property
    def file_modified_content(self):
        return self._file_modified_content
    
    @file_modified_content.setter
    def file_modified_content(self, file_modified_content):
        self._file_modified_content = file_modified_content
        
    @property
    def data_entry_sections(self):
        return self._data_entry_sections
    
    @file_content.setter
    def data_entry_sections(self, data_entry_sections):
        self._data_entry_sections = data_entry_sections
        
    @abstractmethod
    def read_file_sections(self):
        pass
    
    @abstractmethod
    def write_file_sections(self):
        pass