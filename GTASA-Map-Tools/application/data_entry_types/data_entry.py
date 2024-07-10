import os
import re
from abc import ABC, abstractmethod

class DataEntry(ABC):
    def __init__(self, content, index, section, file):
        self._content = content
        self._index = index
        self._section = section
        self._file = file
        self._file_name = file.file_name
        self._file_type = file.file_type

    @property
    def content(self):
        return self._content
    
    @content.setter
    def content(self, content):
        self._content = content
        
    @property
    def index(self):
        return self._index
    
    @index.setter
    def index(self, index):
        self._index = index
        
    @property
    def section(self):
        return self._section
    
    @section.setter
    def section(self, section):
        self._section = section
        
    @property
    def file(self):
        return self._file
    
    @file.setter
    def file(self, file):
        self._file = file
        
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
        
    def get_attributes(self):
        return self.content, self.index, self.section, self.file

    @abstractmethod
    def get_content_elements(self):
        pass
        
    @abstractmethod
    def update_content_element(self, element, element_index):
        pass