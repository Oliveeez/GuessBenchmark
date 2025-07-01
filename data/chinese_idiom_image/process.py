import os

def rename_images_in_folder(folder_path):
    for filename in os.listdir(folder_path):
        if filename.startswith("c_idiom_") and filename.endswith(".jpeg"):
            name_part, ext = os.path.splitext(filename)
            
            parts = name_part.split("_")
            if len(parts) == 3 and parts[0] == "c" and parts[1] == "idiom":
                number = parts[2]
            
                new_filename = f"c_idiom_img_{number}{ext}"
                new_file_path = os.path.join(folder_path, new_filename)
                
                old_file_path = os.path.join(folder_path, filename)
                os.rename(old_file_path, new_file_path)
                print(f"Renamed: {filename} -> {new_filename}")


if __name__ == "__main__":
    folder_path = "/gemini/code/data/chinese_idiom_image/img" 
    rename_images_in_folder(folder_path)