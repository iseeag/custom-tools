from dep_crawl import extract_imports, get_src_file, get_src_files

file_path = 'mockeries/mock_ref.py'
imports = extract_imports(file_path)
src_files = [get_src_file(imp) for imp in imports]
for src_file in src_files:
    imports = extract_imports(src_file)
src_files = get_src_files(file_path)
