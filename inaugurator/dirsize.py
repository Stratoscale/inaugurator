import os
import logging

def get_dir_size_used(dest_root_path):
    st = os.statvfs(dest_root_path)
    used_precent = float((st.f_blocks - st.f_bavail)) / st.f_blocks
    return used_precent

def check_storage_size_over_threshold(dest_root_path, threshold=0.7):
    size = 0
    try:
        size = get_dir_size_used(dest_root_path)
    except Exception as e:
        logging.info("failed to get dir size %s" % (str(e)))
    if size > threshold:
       return True
    return False

#print check_storage_size_over_threshold("/fjfjfj", 0.7)
