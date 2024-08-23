from application.file_types.objects_file import ObjectsFile
from application.data_entry_types.str.data_entry_str import DataEntryStr
from application.data_entry_types.str.ipl.inst import Inst
from application.data_entry_types.str.ipl.cull import Cull
from application.data_entry_types.str.ipl.grge import Grge
from application.data_entry_types.str.ipl.enex import Enex
from application.data_entry_types.str.ipl.pick import Pick
from application.data_entry_types.str.ipl.cars_ipl import CarsIpl
from application.data_entry_types.str.ipl.jump import Jump
from application.data_entry_types.str.ipl.tcyc import Tcyc
from application.data_entry_types.str.ipl.auzo import Auzo
from application.data_entry_types.str.ipl.occl import Occl

class Ipl(ObjectsFile):
    
    def __init__(self, file_name, file_content):
        super().__init__(file_name, file_content)
        self._section_inst = []
        self._section_cull = []
        self._section_path = []
        self._section_grge = []
        self._section_enex = []
        self._section_pick = []
        self._section_cars = []
        self._section_jump = []
        self._section_tcyc = []
        self._section_auzo = []
        self._section_mult = []
        self._section_occl = []
        self._section_zone = []
        
        self.read_file_sections()
        
    @property
    def section_inst(self):
        return self._section_inst

    @section_inst.setter
    def section_inst(self, inst_list):
        if all(isinstance(inst, Inst) for inst in inst_list):
            self._section_inst = inst_list
        else:
            print(f'Called section_inst setter but {inst_list} is not a list of Inst.')
            
    def add_to_section_inst(self, inst_object):
        if isinstance(inst_object, Inst):
            self._section_inst.append(inst_object)
        else:
            print(f'Called add_to_section_inst but {inst_object} is not a Inst object.')
            
    def remove_from_section_inst(self, inst_object):
        if inst_object in self._section_inst:
            if isinstance(inst_object, Inst):
                if inst_object.has_lod:
                    inst_lod_object = next((gta_object for gta_object in self._section_inst if gta_object.internal_id == inst_object.internal_lod_id), None)
                    
                    if inst_lod_object:
                        self._section_inst.remove(inst_lod_object)
                elif inst_object.is_lod:
                    inst_main_object = next((gta_object for gta_object in self._section_inst if gta_object.internal_lod_id == inst_object.internal_id), None)
                    
                    if inst_main_object:
                        inst_main_object.remove_lod()
                    
                self._section_inst.remove(inst_object)
                self.update_section_inst_lods()
            
    def update_section_inst_lods(self):
        ids_to_objects = {gta_object.internal_id: gta_object for gta_object in self._section_inst}

        for inst_object in self._section_inst:
            if inst_object.has_lod:
                inst_lod_object = ids_to_objects.get(inst_object.internal_lod_id)
                if inst_lod_object:
                    inst_object.lod = self._section_inst.index(inst_lod_object)
            
    @property
    def section_cull(self):
        return self._section_cull

    @section_cull.setter
    def section_cull(self, cull_list):
        if all(isinstance(cull, Cull) for cull in cull_list):
            self._section_cull = cull_list
        else:
            print(f'Called section_cull setter but {cull_list} is not a list of Cull.')
            
    def add_to_section_cull(self, cull_object):
        if isinstance(cull_object, Cull):
            self._section_cull.append(cull_object)
        else:
            print(f'Called add_to_section_cull but {cull_object} is not a Cull object.')
            
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
            print(f'Called add_to_section_path  but {path_object} is not a DataEntryStr object.')
            
    @property
    def section_grge(self):
        return self._section_grge

    @section_grge.setter
    def section_grge(self, grge_list):
        if all(isinstance(grge, Grge) for grge in grge_list):
            self._section_grge = grge_list
        else:
            print(f'Called section_grge setter but {grge_list} is not a list of Grge.')
            
    def add_to_section_grge(self, grge_object):
        if isinstance(grge_object, Grge):
            self._section_grge.append(grge_object)
        else:
            print(f'Called add_to_section_grge but {grge_object} is not a Grge object.')
            
    @property
    def section_enex(self):
        return self._section_enex

    @section_enex.setter
    def section_enex(self, enex_list):
        if all(isinstance(enex, Enex) for enex in enex_list):
            self._section_enex = enex_list
        else:
            print(f'Called section_enex setter but {enex_list} is not a list of Enex.')
            
    def add_to_section_enex(self, enex_object):
        if isinstance(enex_object, Enex):
            self._section_enex.append(enex_object)
        else:
            print(f'Called add_to_section_enex but {enex_object} is not a Enex object.')
            
    @property
    def section_pick(self):
        return self._section_pick

    @section_pick.setter
    def section_pick(self, pick_list):
        if all(isinstance(pick, Pick) for pick in pick_list):
            self._section_pick = pick_list
        else:
            print(f'Called section_pick setter but {pick_list} is not a list of Pick.')
            
    def add_to_section_pick(self, pick_object):
        if isinstance(pick_object, Pick):
            self._section_pick.append(pick_object)
        else:
            print(f'Called add_to_section_pick but {pick_object} is not a Pick object.')
            
    @property
    def section_cars(self):
        return self._section_cars

    @section_cars.setter
    def section_cars(self, cars_list):
        if all(isinstance(cars, CarsIpl) for cars in cars_list):
            self._section_cars = cars_list
        else:
            print(f'Called section_cars setter but {cars_list} is not a list of Cars.')
            
    def add_to_section_cars(self, cars_object):
        if isinstance(cars_object, CarsIpl):
            self._section_cars.append(cars_object)
        else:
            print(f'Called add_to_section_cars but {cars_object} is not a Cars object.')
            
    @property
    def section_jump(self):
        return self._section_jump

    @section_jump.setter
    def section_jump(self, jump_list):
        if all(isinstance(jump, Jump) for jump in jump_list):
            self._section_jump = jump_list
        else:
            print(f'Called section_jump setter but {jump_list} is not a list of Jump.')
            
    def add_to_section_jump(self, jump_object):
        if isinstance(jump_object, Jump):
            self._section_jump.append(jump_object)
        else:
            print(f'Called add_to_section_jump but {jump_object} is not a Jump object.')
            
    @property
    def section_tcyc(self):
        return self._section_tcyc

    @section_tcyc.setter
    def section_tcyc(self, tcyc_list):
        if all(isinstance(tcyc, Tcyc) for tcyc in tcyc_list):
            self._section_tcyc = tcyc_list
        else:
            print(f'Called section_tcyc setter but {tcyc_list} is not a list of Tcyc.')
            
    def add_to_section_tcyc(self, tcyc_object):
        if isinstance(tcyc_object, Tcyc):
            self._section_tcyc.append(tcyc_object)
        else:
            print(f'Called add_to_section_tcyc but {tcyc_object} is not a Tcyc object.')
            
    @property
    def section_auzo(self):
        return self._section_auzo

    @section_auzo.setter
    def section_auzo(self, auzo_list):
        if all(isinstance(auzo, Auzo) for auzo in auzo_list):
            self._section_auzo = auzo_list
        else:
            print(f'Called section_auzo setter but {auzo_list} is not a list of Auzo.')
            
    def add_to_section_auzo(self, auzo_object):
        if isinstance(auzo_object, Auzo):
            self._section_auzo.append(auzo_object)
        else:
            print(f'Called add_to_section_auzo but {auzo_object} is not a Auzo object.')
            
    @property
    def section_mult(self):
        return self._section_mult

    @section_mult.setter
    def section_mult(self, mult_list):
        if all(isinstance(mult, DataEntryStr) for mult in mult_list):
            self._section_mult = mult_list
        else:
            print(f'Called section_mult setter but {mult_list} is not a list of DataEntryStr.')
            
    def add_to_section_mult(self, mult_object):
        if isinstance(mult_object, DataEntryStr):
            self._section_mult.append(mult_object)
        else:
            print(f'Called add_to_section_mult  but {mult_object} is not a DataEntryStr object.')
            
    @property
    def section_occl(self):
        return self._section_occl

    @section_occl.setter
    def section_occl(self, occl_list):
        if all(isinstance(occl, Occl) for occl in occl_list):
            self._section_occl = occl_list
        else:
            print(f'Called section_occl setter but {occl_list} is not a list of Occl.')
            
    def add_to_section_occl(self, occl_object):
        if isinstance(occl_object, Occl):
            self._section_occl.append(occl_object)
        else:
            print(f'Called add_to_section_occl but {occl_object} is not a Occl object.')
            
    @property
    def section_zone(self):
        return self._section_zone

    @section_zone.setter
    def section_zone(self, zone_list):
        if all(isinstance(zone, DataEntryStr) for zone in zone_list):
            self._section_zone = zone_list
        else:
            print(f'Called section_zone setter but {zone_list} is not a list of DataEntryStr.')
            
    def add_to_section_zone(self, zone_object):
        if isinstance(zone_object, DataEntryStr):
            self._section_zone.append(zone_object)
        else:
            print(f'Called add_to_section_zone  but {zone_object} is not a DataEntryStr object.')
            
    def read_file_sections(self):
        current_section = None
        line_position = -1
        
        for line in self.file_content:
            data_entry = DataEntryStr(line, line_position, None, self)
            
            if data_entry.is_ipl_section_starter():
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
            
            if data_entry.is_valid_ipl_object():
                data_entry.index += 1
                line_position = data_entry.index
                
                if current_section == 'inst':
                    gta_object = Inst(*data_entry.get_attributes())
                    self.add_to_section_inst(gta_object)
                elif current_section == 'cull':
                    gta_object = Cull(*data_entry.get_attributes())
                    self.add_to_section_cull(gta_object)
                elif current_section == 'path':
                    self.add_to_section_path(data_entry)
                elif current_section == 'grge':
                    gta_object = Grge(*data_entry.get_attributes())
                    self.add_to_section_grge(gta_object)
                elif current_section == 'enex':
                    gta_object = Enex(*data_entry.get_attributes())
                    self.add_to_section_enex(gta_object)
                elif current_section == 'pick':
                    gta_object = Pick(*data_entry.get_attributes())
                    self.add_to_section_pick(gta_object)
                elif current_section == 'cars':
                    gta_object = CarsIpl(*data_entry.get_attributes())
                    self.add_to_section_cars(gta_object)
                elif current_section == 'jump':
                    gta_object = Jump(*data_entry.get_attributes())
                    self.add_to_section_jump(gta_object)
                elif current_section == 'tcyc':
                    gta_object = Tcyc(*data_entry.get_attributes())
                    self.add_to_section_tcyc(gta_object)
                elif current_section == 'auzo':
                    gta_object = Auzo(*data_entry.get_attributes())
                    self.add_to_section_auzo(gta_object)
                elif current_section == 'mult':
                    self.add_to_section_mult(data_entry)
                elif current_section == 'occl':
                    gta_object = Occl(*data_entry.get_attributes())
                    self.add_to_section_occl(gta_object)
                elif current_section == 'zone':
                    self.add_to_section_zone(data_entry)
                    
        if self.section_inst:
            for gta_object in self.section_inst:
                if gta_object.has_lod and gta_object.lod < len(self.section_inst):
                    related_gta_object = self.section_inst[gta_object.lod]
                    gta_object.internal_lod_id = related_gta_object.internal_id
                    related_gta_object.is_lod = True
                    
    def write_file_sections(self):
        file_content = ''
        
        if self.section_inst:
            file_content += 'inst' + '\n'
            for gta_object in self.section_inst:
                file_content += gta_object.content + '\n'
            file_content += 'end' + '\n'
        if self.section_auzo:
            file_content += 'auzo' + '\n'
            for gta_object in self.section_auzo:
                file_content += gta_object.content + '\n'
            file_content += 'end' + '\n'
        if self.section_cars:
            file_content += 'cars' + '\n'
            for gta_object in self.section_cars:
                file_content += gta_object.content + '\n'
            file_content += 'end' + '\n'
        if self.section_cull:
            file_content += 'cull' + '\n'
            for gta_object in self.section_cull:
                file_content += gta_object.content + '\n'
            file_content += 'end' + '\n'
        if self.section_enex:
            file_content += 'enex' + '\n'
            for gta_object in self.section_enex:
                file_content += gta_object.content + '\n'
            file_content += 'end' + '\n'
        if self.section_grge:
            file_content += 'grge' + '\n'
            for gta_object in self.section_grge:
                file_content += gta_object.content + '\n'
            file_content += 'end' + '\n'
        if self.section_jump:
            file_content += 'jump' + '\n'
            for gta_object in self.section_jump:
                file_content += gta_object.content + '\n'
            file_content += 'end' + '\n'
        if self.section_occl:
            file_content += 'occl' + '\n'
            for gta_object in self.section_occl:
                file_content += gta_object.content + '\n'
            file_content += 'end' + '\n'
        if self.section_pick:
            file_content += 'pick' + '\n'
            for gta_object in self.section_pick:
                file_content += gta_object.content + '\n'
            file_content += 'end' + '\n'
        if self.section_tcyc:
            file_content += 'tcyc' + '\n'
            for gta_object in self.section_tcyc:
                file_content += gta_object.content + '\n'
            file_content += 'end' + '\n'
            
        self.file_modified_content = file_content
        return self.file_modified_content