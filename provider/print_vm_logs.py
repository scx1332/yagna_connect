import os

search_dir = "/root/.local/share/ya-provider/exe-unit/work"
dirs = []
for dir in os.listdir(search_dir):
    if dir == "logs":
        continue
    dirs.append(dir)

if len(dirs) > 0:
    dirs.sort(key=lambda x: os.path.getmtime(os.path.join(search_dir, x)))
    full_dir = os.path.join(search_dir, dirs[-1])
    subdir = os.listdir(full_dir)
    for sub in subdir:
        log_dir = os.path.join(full_dir, sub, "logs")
        if os.path.isdir(log_dir):
            for file in os.listdir(log_dir):
                if file.startswith("ya-runtime-vm"):
                    target_log_file = os.path.join(log_dir, file)
                    with open(target_log_file) as f:
                        print(f"Logs from: {target_log_file}")
                        print(f.read())