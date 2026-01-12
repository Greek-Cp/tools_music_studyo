filename = r"c:\Users\denis\Documents\GitHub\studyo_music_library\pubspec.yaml"
with open(filename, 'r') as f:
    for i, line in enumerate(f):
        if "assets/sounds/" in line:
            print(f"{i+1}: {line.rstrip()}")
