from application.file_types.objects_file import ObjectsFile
from application.data_entry_types.str.ide.objs import Objs
from application.data_entry_types.str.ide.tobj import Tobj
from application.data_entry_types.str.ide.anim import Anim
from application.data_entry_types.str.data_entry_str import DataEntryStr

class Ide(ObjectsFile):
    
    def __init__(self, file_name, file_content):
        super().__init__(file_name, file_content)
        self._section_objs = []
        self._section_tobj = []
        self._section_path = []
        self._section_2dfx = []
        self._section_anim = []
        self._section_txdp = []
        self._section_cars = []
        self._section_hier = []
        self._section_peds = []
        self._section_weap = []
        
        self.read_file_sections()
    
    @property
    def section_objs(self):
        return self._section_objs

    @section_objs.setter
    def section_objs(self, objs_list):
        if all(isinstance(objs, Objs) for objs in objs_list):
            self._section_objs = objs_list
        else:
            print(f'Called section_objs setter but {objs_list} is not a list of Objs.')
            
    def add_to_section_objs(self, objs_object):
        if isinstance(objs_object, Objs):
            self._section_objs.append(objs_object)
        else:
            print(f'Called add_to_section_objs but {objs_object} is not a Objs object.')

    @property
    def section_tobj(self):
        return self._section_tobj

    @section_tobj.setter
    def section_tobj(self, tobj_list):
        if all(isinstance(tobj, Tobj) for tobj in tobj_list):
            self._section_tobj = tobj_list
        else:
            print(f'Called section_tobj setter but {tobj_list} is not a list of Tobj.')
            
    def add_to_section_tobj(self, tobj_object):
        if isinstance(tobj_object, Tobj):
            self._section_tobj.append(tobj_object)
        else:
            print(f'Called add_to_section_tobj but {tobj_object} is not a Tobj object.')
            
    @property
    def section_path(self):
        return self._section_path

    @section_path.setter
    def section_path(self, path_list):
        if all(isinstance(path, DataEntryStr) for path in path_list):
            self._section_path = path_list
        else:
            print(f'Called section_path setter but {path_list} is not a list of DataEntryStr.')
            
    def add_to_section_path(self, path_object):
        if isinstance(path_object, DataEntryStr):
            self._section_path.append(path_object)
        else:
            print(f'Called add_to_section_path but {path_object} is not a DataEntryStr object.')
            
    @property
    def section_2dfx(self):
        return self._section_2dfx

    @section_2dfx.setter
    def section_2dfx(self, fx2d_list):
        if all(isinstance(fx2d, DataEntryStr) for fx2d in fx2d_list):
            self._section_2dfx = fx2d_list
        else:
            print(f'Called section_2dfx setter but {fx2d_list} is not a list of DataEntryStr.')
            
    def add_to_section_2dfx(self, fx2d_object):
        if isinstance(fx2d_object, DataEntryStr):
            self._section_2dfx.append(fx2d_object)
        else:
            print(f'Called add_to_section_2dfx but {fx2d_object} is not a DataEntryStr object.')
            
    @property
    def section_anim(self):
        return self._section_anim

    @section_anim.setter
    def section_anim(self, anim_list):
        if all(isinstance(anim, Anim) for anim in anim_list):
            self._section_anim = anim_list
        else:
            print(f'Called section_anim setter but {anim_list} is not a list of Anim.')
            
    def add_to_section_anim(self, anim_object):
        if isinstance(anim_object, Anim):
            self._section_anim.append(anim_object)
        else:
            print(f'Called add_to_section_anim but {anim_object} is not a Anim object.')
            
    @property
    def section_txdp(self):
        return self._section_txdp

    @section_txdp.setter
    def section_txdp(self, txdp_list):
        if all(isinstance(txdp, DataEntryStr) for txdp in txdp_list):
            self._section_txdp = txdp_list
        else:
            print(f'Called section_txdp setter but {txdp_list} is not a list of DataEntryStr.')
            
    def add_to_section_txdp(self, txdp_object):
        if isinstance(txdp_object, DataEntryStr):
            self._section_txdp.append(txdp_object)
        else:
            print(f'Called add_to_section_txdp but {txdp_object} is not a DataEntryStr object.')
            
    @property
    def section_cars(self):
        return self._section_cars

    @section_cars.setter
    def section_cars(self, cars_list):
        if all(isinstance(cars, DataEntryStr) for cars in cars_list):
            self._section_cars = cars_list
        else:
            print(f'Called section_cars setter but {cars_list} is not a list of DataEntryStr.')
            
    def add_to_section_cars(self, cars_object):
        if isinstance(cars_object, DataEntryStr):
            self._section_cars.append(cars_object)
        else:
            print(f'Called add_to_section_cars  but {cars_object} is not a DataEntryStr object.')
            
    @property
    def section_hier(self):
        return self._section_hier

    @section_hier.setter
    def section_hier(self, hier_list):
        if all(isinstance(hier, DataEntryStr) for hier in hier_list):
            self._section_hier = hier_list
        else:
            print(f'Called section_hier setter but {hier_list} is not a list of DataEntryStr.')
            
    def add_to_section_hier(self, hier_object):
        if isinstance(hier_object, DataEntryStr):
            self._section_hier.append(hier_object)
        else:
            print(f'Called add_to_section_hier  but {hier_object} is not a DataEntryStr object.')
            
    @property
    def section_peds(self):
        return self._section_peds

    @section_peds.setter
    def section_peds(self, peds_list):
        if all(isinstance(peds, DataEntryStr) for peds in peds_list):
            self._section_peds = peds_list
        else:
            print(f'Called section_peds setter but {peds_list} is not a list of DataEntryStr.')
            
    def add_to_section_peds(self, peds_object):
        if isinstance(peds_object, DataEntryStr):
            self._section_peds.append(peds_object)
        else:
            print(f'Called add_to_section_peds  but {peds_object} is not a DataEntryStr object.')
            
    @property
    def section_weap(self):
        return self._section_weap

    @section_weap.setter
    def section_weap(self, weap_list):
        if all(isinstance(weap, DataEntryStr) for weap in weap_list):
            self._section_weap = weap_list
        else:
            print(f'Called section_weap setter but {weap_list} is not a list of DataEntryStr.')
            
    def add_to_section_weap(self, weap_object):
        if isinstance(weap_object, DataEntryStr):
            self._section_weap.append(weap_object)
        else:
            print(f'Called add_to_section_weap  but {weap_object} is not a DataEntryStr object.')
            
    def read_file_sections(self):
        current_section = None
        line_position = -1
        
        for line in self.file_content:
            data_entry = DataEntryStr(line, line_position, None, self)
            
            if data_entry.is_ide_section_starter():
                data_entry.section = data_entry.formatted_line()
                current_section = data_entry.section
                continue
                
            if data_entry.is_section_finalizer():
                data_entry.section = None
                current_section = data_entry.section
                data_entry.index = -1
                line_position = data_entry.index
                
                continue
            
            if not current_section is None:
                data_entry.section = current_section
            
            if data_entry.is_valid_ide_object():
                data_entry.index += 1
                line_position = data_entry.index
                
                if current_section == 'objs':
                    gta_object = Objs(*data_entry.get_attributes())
                    self.add_to_section_objs(gta_object)
                elif current_section == 'tobj':
                    gta_object = Tobj(*data_entry.get_attributes())
                    self.add_to_section_tobj(gta_object)
                elif current_section == 'anim':
                    gta_object = Anim(*data_entry.get_attributes())
                    self.add_to_section_anim(gta_object)
                elif (current_section == 'path'):
                    self.add_to_section_path(data_entry)
                elif (current_section == '2dfx'):
                    self.add_to_section_2dfx(data_entry)
                elif (current_section == 'txdp'):
                    self.add_to_section_txdp(data_entry)
                elif (current_section == 'cars'):
                    self.add_to_section_cars(data_entry)
                elif (current_section == 'hier'):
                    self.add_to_section_hier(data_entry)
                elif (current_section == 'peds'):
                    self.add_to_section_peds(data_entry)
                elif (current_section == 'weap'):
                    self.add_to_section_weap(data_entry)
                    
    def write_file_sections(self):
        file_content = ''
        
        if self.section_objs:
            file_content += 'objs' + '\n'
            for gta_object in self.section_objs:
                file_content += gta_object.content + '\n'
            file_content += 'end' + '\n'
        if self.section_tobj:
            file_content += 'tobj' + '\n'
            for gta_object in self.section_tobj:
                file_content += gta_object.content + '\n'
            file_content += 'end' + '\n'
        if self.section_anim:
            file_content += 'anim' + '\n'
            for gta_object in self.section_anim:
                file_content += gta_object.content + '\n'
            file_content += 'end' + '\n'
        if self.section_path:
            file_content += 'path' + '\n'
            for gta_object in self.section_path:
                file_content += gta_object.content + '\n'
            file_content += 'end' + '\n'
        if self.section_2dfx:
            file_content += '2dfx' + '\n'
            for gta_object in self.section_2dfx:
                file_content += gta_object.content + '\n'
            file_content += 'end' + '\n'
        if self.section_txdp:
            file_content += 'txdp' + '\n'
            for gta_object in self.section_txdp:
                file_content += gta_object.content + '\n'
            file_content += 'end' + '\n'
        if self.section_cars:
            file_content += 'cars' + '\n'
            for gta_object in self.section_cars:
                file_content += gta_object.content + '\n'
            file_content += 'end' + '\n'
        if self.section_hier:
            file_content += 'hier' + '\n'
            for gta_object in self.section_hier:
                file_content += gta_object.content + '\n'
            file_content += 'end' + '\n'
        if self.section_peds:
            file_content += 'peds' + '\n'
            for gta_object in self.section_peds:
                file_content += gta_object.content + '\n'
            file_content += 'end' + '\n'
        if self.section_weap:
            file_content += 'weap' + '\n'
            for gta_object in self.section_weap:
                file_content += gta_object.content + '\n'
            file_content += 'end' + '\n'
            
        self.file_modified_content = file_content
        return self.file_modified_content