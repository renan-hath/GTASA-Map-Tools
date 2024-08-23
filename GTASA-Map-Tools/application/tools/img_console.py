import subprocess
import time
import os
from queue import Queue, Empty
from threading import Thread

class IMGConsole:
    
    RESOURCES_DIR = "resources"
    IMG_CONSOLE_NAME = "fastman92ImgConsole32.exe"
    IMG_CONSOLE_DIR = os.path.join(RESOURCES_DIR, "IMGconsole_32-bit")
    IMG_CONSOLE_PATH = os.path.join(IMG_CONSOLE_DIR, IMG_CONSOLE_NAME)
    IMG_CONSOLE_TEMP_DIR = IMG_CONSOLE_DIR + "\\" + "Temp"
    
    def __init__(self):
        self.process = None
        self.queue = Queue()
        self.output_thread = None
        self._img_file_path = ''

    def start(self):
        if not self.process:
            self.process = subprocess.Popen(self.IMG_CONSOLE_PATH, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)
            # Inicia um thread para ler o stdout não bloqueante
            self.output_thread = Thread(target=self._enqueue_output, args=(self.process.stdout, self.queue))
            self.output_thread.daemon = True  # O thread será encerrado quando o programa principal terminar
            self.output_thread.start()
            time.sleep(1)  # Aguarda o prompt interativo

    def _enqueue_output(self, out, queue):
        for line in iter(out.readline, ''):
            queue.put(line.strip())
        out.close()

    def send_command(self, command):
        if not self.process:
            raise RuntimeError("Process not started. Call start() method first.")
        
        self.process.stdin.write(command + '\n')
        self.process.stdin.flush()
        
        output_list = []
        total_sleep_time = 0
        max_sleep_time = 3
        
        while total_sleep_time < max_sleep_time:
            try:
                # Tenta ler da fila sem bloquear
                output = self.queue.get_nowait()
                
                if output.strip():
                    total_sleep_time = 0
                    output_list.append(output)
                    print(output)
                else:
                    time.sleep(0.1)
                    total_sleep_time += 0.1
            except Empty:
                time.sleep(0.1)
                total_sleep_time += 0.1
            
        return output_list
    
    def close(self):
        if self.process:
            self.process.stdin.write('-exit\n')
            self.process.stdin.flush()
            
            # Adiciona o comando à fila
            self.queue.put('-exit')

            # Aguarda a saída do comando e o fechamento do processo
            output_list = []
            while True:
                try:
                    # Tenta ler da fila sem bloquear
                    output = self.queue.get_nowait()
                    output_list.append(output)
                except Empty:
                    # Se a fila estiver vazia, aguarda um pouco e tenta novamente
                    time.sleep(0.1)
                    
                    if not self.process.poll() is None and self.queue.empty():
                        break
            
            self.process = None

    def open_img(self, img_file_path):
        file_name = os.path.basename(img_file_path)
        
        if not os.path.exists(img_file_path):
            print(f"IMG Console - Error when trying to open {file_name}. The file does not exist.")
            return False
        
        corrected_img_file_path = img_file_path.replace("\\", "\\\\")
        command = f'-open "{corrected_img_file_path}"'
        output = self.send_command(command)
        success_message = f'Archive "{img_file_path}" opened.'
        
        if any(success_message in line for line in output):
            print(f"IMG Console - Opened {file_name}")
            return True
        else:
            print(f"IMG Console - Error when trying to open {file_name}")
            print("Output:", "\n".join(output))
            return False

    def rebuild(self, img_file_path):
        file_name = os.path.basename(img_file_path)
        command = f'-rebuildIfArchiveWasModified'
        output = self.send_command(command)
        success_message = f'Archive rebuilt successfully'
        
        if any(success_message in line for line in output):
            print(f"IMG Console - Rebuilt {file_name}")
            return output
        else:
            print(f"IMG Console - Error when trying to rebuild {file_name}")
            print("Output:", "\n".join(output))
            return False

    def print_list_of_entries(self, img_file_path):
        file_name = os.path.basename(img_file_path)
        command = f'-printListOfEntries'
        output = self.send_command(command)
        success_message = f'List of entries'
        
        if any(success_message in line for line in output):
            print(f"IMG Console - Printed {file_name} entries")
            return output
        else:
            print(f"IMG Console - Error when trying to print {file_name} entries")
            print("Output:", "\n".join(output))
            return False
        
    def has_files(self, img_file_path):
        sa_img_entries = self.print_list_of_entries(img_file_path)
        
        if sa_img_entries:
            for entry in sa_img_entries:
                if "Name:" and "OriginalSizeInBytes:" in entry:
                    return True
        
        return False
        
    def export_to_temp(self, file_name):
        os.makedirs(self.IMG_CONSOLE_TEMP_DIR, exist_ok=True)
        corrected_output_path = os.path.abspath(self.IMG_CONSOLE_TEMP_DIR).replace("\\", "\\\\")
        command = f'-export "{file_name}" "{corrected_output_path}"'
        output = self.send_command(command)
        success_message = f'File {file_name} exported successfully'
        
        if any(success_message in line for line in output):
            print(f"IMG Console - Exported {file_name} to temporary folder")
            return output
        else:
            print(f"IMG Console - Error when trying to export {file_name} to temporary folder")
            print("Output:", "\n".join(output))
            return False
        
    def export(self, file_name, output_path):
        os.makedirs(output_path, exist_ok=True)
        corrected_output_path = os.path.abspath(output_path).replace("\\", "\\\\")
        command = f'-export "{file_name}" "{corrected_output_path}"'
        output = self.send_command(command)
        success_message = f'File {file_name} exported successfully'
        
        if any(success_message in line for line in output):
            print(f"IMG Console - Exported {file_name} to {output_path}")
            return output
        else:
            print(f"IMG Console - Error when trying to export {file_name} to {output_path}")
            print("Output:", "\n".join(output))
            return False
        
    def export_all(self, img_file_path, output_path):
        os.makedirs(output_path, exist_ok=True)
        file_name = os.path.basename(img_file_path)
        corrected_output_path = os.path.abspath(output_path).replace("\\", "\\\\")
        command = f'-exportAll "{corrected_output_path}"'
        output = self.send_command(command)
        success_message = f'exported successfully'
        
        if any(success_message in line for line in output):
            print(f"IMG Console - Exported all files from {file_name} to {output_path}")
            return output
        else:
            print(f"IMG Console - Error when trying to export all files from {file_name} to {output_path}")
            print("Output:", "\n".join(output))
            return False
        
    def import_all(self, img_file_path, input_path):
        file_name = os.path.basename(img_file_path)
        
        if not os.path.exists(input_path):
            print(f"IMG Console - Error when trying to import to {file_name} from {input_path}. The input directory does not exist.")
            return False
        
        if not any(os.listdir(input_path)):
            print(f"IMG Console - Error when trying to import to {file_name} from {input_path}. There are no files in the input directory.")
            return False
        
        corrected_input_path = os.path.abspath(input_path).replace("\\", "\\\\")
        command = f'-importFromDirectory "{corrected_input_path}"'
        output = self.send_command(command)
        success_message = f'Imported file:'
        
        if any(success_message in line for line in output):
            print(f"IMG Console - Imported all files from {input_path} to {file_name}")
            return output
        else:
            print(f"IMG Console - Error when trying to import all files from {input_path} to {file_name}")
            print("Output:", "\n".join(output))
            return False
        
    def import_file(self, img_file_path, file_path):
        img_file_name = os.path.basename(img_file_path)
        file_name = os.path.basename(file_path)
        
        if not os.path.exists(file_path):
            print(f"IMG Console - Error when trying to import {file_name} to {img_file_name}. The file to import does not exist.")
            return False
        
        corrected_file_path = os.path.abspath(file_path).replace("\\", "\\\\")
        command = f'-import "{corrected_file_path}"'
        output = self.send_command(command)
        success_message = f'Imported file:'
        
        if any(success_message in line for line in output):
            print(f"IMG Console - Imported {file_name} to {img_file_name}")
            return output
        else:
            print(f"IMG Console - Error when trying to import {file_name} to {img_file_name}")
            print("Output:", "\n".join(output))
            return False
        
    def delete_all(self, img_file_path):
        file_name = os.path.basename(img_file_path)
        command = f'-deleteAllFiles'
        output = self.send_command(command)
        success_message = f'All files have been deleted from archive.'
        
        if any(success_message in line for line in output):
            print(f"IMG Console - Deleted all files from {file_name}")
            return output
        else:
            print(f"IMG Console - Error when trying to delete all files from {file_name}")
            print("Output:", "\n".join(output))
            return False
        
    def delete(self, file_name):
        command = f'-delete "{file_name}"'
        output = self.send_command(command)
        success_message = f'Removed file {file_name}'
        
        if any(success_message in line for line in output):
            print(f"IMG Console - Deleted {file_name}")
            return output
        else:
            print(f"IMG Console - Error when trying to delete {file_name}")
            print("Output:", "\n".join(output))
            return False
        
    def rename(self, file_name, file_new_name):
        command = f'-rename "{file_name}" "{file_new_name}"'
        output = self.send_command(command)
        success_message = f'Renamed file {file_name} to {file_new_name}'
        
        if any(success_message in line for line in output):
            print(f"IMG Console - Renamed {file_name} to {file_new_name}")
            return output
        else:
            print(f"IMG Console - Error when trying to rename {file_name} to {file_new_name}")
            print("Output:", "\n".join(output))
            return False
        
    def replace(self, files_path):
        corrected_files_path = os.path.abspath(files_path).replace("\\", "\\\\")
        command = f'-replaceFromDirectory "{corrected_files_path}"'
        output = self.send_command(command)
        success_message = f'Replaced file:'
        
        if any(success_message in line for line in output):
            print(f"IMG Console - Replaced files from {files_path}")
            return output
        else:
            print(f"IMG Console - Error when trying to replace files from {files_path}")
            print("Output:", "\n".join(output))
            return False