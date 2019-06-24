from __future__ import division
from __future__ import print_function

import os
import sys
import ctsb
from urllib import request
from urllib.error import URLError
from urllib.request import urlretrieve

# important - get absolute path of package directory
def get_ctsb_dir():
    init_dir = os.path.abspath(ctsb.__file__)
    ctsb_dir = init_dir.rsplit('/', 1)[0]
    return ctsb_dir

def report_download_progress(chunk_number, chunk_size, file_size):
    """
    Prints out the download progress bar
    Args:
        chunk_number(int): chunk number
        chunk_size(int): maximize size of a chunk
        file_size(int): total size of download
    """
    if file_size != -1:
        percent = min(1, (chunk_number * chunk_size) / file_size)
        bar = '#' * int(64 * percent)
        sys.stdout.write('\r0% |{:<64}| {}%'.format(bar, int(percent * 100)))

def download(destination_path, url, verbose):
    """
    Downloads the file at url to destination_path
    Args:
        destination_path(string): the destination path of the download
        url(string): the url of the file to download
        verbose(boolean): If True, will report download progress and inform if download already exists
    """
    if os.path.exists(destination_path):
        if verbose:
            print('{} already exists, skipping ...'.format(destination_path))
    else:
        if verbose:
            print('Downloading {} ...'.format(url))
        try:
            hook = report_download_progress if verbose else None
            urlretrieve(url, destination_path, reporthook=hook)
        except URLError:
            raise RuntimeError('Error downloading resource!')
        finally:
            if verbose:
                # Just a newline.
                print()
