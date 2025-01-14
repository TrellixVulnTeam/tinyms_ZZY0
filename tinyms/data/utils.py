# Copyright 2021 Huawei Technologies Co., Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ============================================================================
"""TinyMS data utils package."""
import os
import sys
import gzip
import tarfile
import requests
import wget
from PIL import Image
import numpy as np
from tinyms import Tensor

__all__ = ['download_dataset', 'generate_image_list', 'load_resized_img', 'load_img']

IMG_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.ppm', '.bmp', '.tif', '.tiff']


def is_image(filename):
    """
    Judge whether it is a picture.

    Args:
        filename (str): image name.

    Returns:
        bool, True or False.

    """
    return any(filename.lower().endswith(extension) for extension in IMG_EXTENSIONS)


def generate_image_list(dir_path, max_dataset_size=float("inf")):
    """
    Traverse the directory to generate a list of images path.

    Args:
        dir_path (str): image directory.
        max_dataset_size (int): Maximum number of return image paths.

    Returns:
        Image path list.

    """
    images = []
    assert os.path.isdir(dir_path), '%s is not a valid directory' % dir_path

    for root, _, fnames in sorted(os.walk(dir_path)):
        for fname in fnames:
            if is_image(fname):
                path = os.path.join(root, fname)
                images.append(path)

    print("len(images):", len(images))
    return images[:min(max_dataset_size, len(images))]


def _unzip(gzip_path):
    """unzip dataset file
    Args:
        gzip_path: dataset file path
    """
    # decompress the file if gzip_path ends with `.tar`
    if gzip_path.endswith('.tar'):
        with tarfile.open(gzip_path) as f:
            def is_within_directory(directory, target):
                
                abs_directory = os.path.abspath(directory)
                abs_target = os.path.abspath(target)
            
                prefix = os.path.commonprefix([abs_directory, abs_target])
                
                return prefix == abs_directory
            
            def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
            
                for member in tar.getmembers():
                    member_path = os.path.join(path, member.name)
                    if not is_within_directory(path, member_path):
                        raise Exception("Attempted Path Traversal in Tar File")
            
                tar.extractall(path, members, numeric_owner=numeric_owner) 
                
            
            safe_extract(f, gzip_path[:gzip_path.rfind("/")])
    elif gzip_path.endswith('.gz'):
        gzip_file = gzip_path.replace('.gz', '')
        with open(gzip_file, 'wb') as f:
            gz_file = gzip.GzipFile(gzip_path)
            f.write(gz_file.read())
        # decompress the file if gz_file ends with `.tar`
        if gzip_file.endswith('.tar'):
            with tarfile.open(gzip_file) as f:
                def is_within_directory(directory, target):
                    
                    abs_directory = os.path.abspath(directory)
                    abs_target = os.path.abspath(target)
                
                    prefix = os.path.commonprefix([abs_directory, abs_target])
                    
                    return prefix == abs_directory
                
                def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
                
                    for member in tar.getmembers():
                        member_path = os.path.join(path, member.name)
                        if not is_within_directory(path, member_path):
                            raise Exception("Attempted Path Traversal in Tar File")
                
                    tar.extractall(path, members, numeric_owner=numeric_owner) 
                    
                
                safe_extract(f, gzip_file[:gzip_file.rfind("/")])
    else:
        print("Currently the format of unzip dataset only supports `*.tar`, `*.gz` and `*.tar.gz`!")
        sys.exit(0)


def _fetch_and_unzip(url, file_name):
    """download the dataset from remote url
    Args:
        url: str, remote download url
        file_name: str, local path of downloaded file
    """
    res = requests.get(url, stream=True, verify=False)
    # get dataset size
    total_size = int(res.headers["Content-Length"])
    temp_size = 0
    with open(file_name, "wb+") as f:
        for chunk in res.iter_content(chunk_size=1024):
            temp_size += len(chunk)
            f.write(chunk)
            f.flush()
            done = int(100 * temp_size / total_size)
            # show download progress
            sys.stdout.write("\r[{}{}] {:.2f}%".format("█" * done, " " * (100 - done), 100 * temp_size / total_size))
            sys.stdout.flush()
    print("\n============== {} is ready ==============".format(file_name))
    _unzip(file_name)
    os.remove(file_name)


def _fetch_and_unzip_by_wget(url, file_name):
    """download the dataset from remote url by wget tool
    Args:
        url: str, remote download url
        file_name: str, local path of downloaded file
    """
    # function to show download progress
    def bar_progress(current, total, width=80):
        progress_message = "Downloading: %d%% [%d / %d] bytes" % (current / total * 100, current, total)
        # Don't use print() as it will print in new line every time.
        sys.stdout.write("\r" + progress_message)
        sys.stdout.flush()
    # using wget is faster than fetch.
    wget.download(url, out=file_name, bar=bar_progress)
    print("\n============== {} is ready ==============".format(file_name))
    _unzip(file_name)
    os.remove(file_name)


def _download_mnist(local_path):
    """Download the dataset from http://yann.lecun.com/exdb/mnist/."""
    dataset_path = os.path.join(local_path, 'mnist')
    train_path = os.path.join(dataset_path, 'train')
    test_path = os.path.join(dataset_path, 'test')
    if not os.path.exists(train_path):
        os.makedirs(train_path)
    if not os.path.exists(test_path):
        os.makedirs(test_path)
    print("************** Downloading the MNIST dataset **************")
    train_url = {"http://yann.lecun.com/exdb/mnist/train-images-idx3-ubyte.gz",
                 "http://yann.lecun.com/exdb/mnist/train-labels-idx1-ubyte.gz"}
    test_url = {"http://yann.lecun.com/exdb/mnist/t10k-images-idx3-ubyte.gz",
                "http://yann.lecun.com/exdb/mnist/t10k-labels-idx1-ubyte.gz"}
    for url in train_url:
        # split the file name from url
        file_name = os.path.join(train_path, url.split('/')[-1])
        if not os.path.exists(file_name.replace('.gz', '')):
            _fetch_and_unzip(url, file_name)
    for url in test_url:
        # split the file name from url
        file_name = os.path.join(test_path, url.split('/')[-1])
        if not os.path.exists(file_name.replace('.gz', '')):
            _fetch_and_unzip(url, file_name)

    return dataset_path


def _download_cifar10(local_path):
    '''Download the dataset from http://www.cs.toronto.edu/~kriz/cifar.html.'''
    dataset_path = os.path.join(local_path, 'cifar10')
    if not os.path.exists(dataset_path):
        os.makedirs(dataset_path)

    print("************** Downloading the Cifar10 dataset **************")
    remote_url = "http://www.cs.toronto.edu/~kriz/cifar-10-binary.tar.gz"
    file_name = os.path.join(dataset_path, remote_url.split('/')[-1])
    if not os.path.exists(file_name.replace('.gz', '')):
        _fetch_and_unzip(remote_url, file_name)

    return os.path.join(dataset_path, 'cifar-10-batches-bin')


def _download_cifar100(local_path):
    '''Download the dataset from http://www.cs.toronto.edu/~kriz/cifar.html.'''
    dataset_path = os.path.join(local_path, 'cifar100')
    if not os.path.exists(dataset_path):
        os.makedirs(dataset_path)

    print("************** Downloading the Cifar100 dataset **************")
    remote_url = "http://www.cs.toronto.edu/~kriz/cifar-100-binary.tar.gz"
    file_name = os.path.join(dataset_path, remote_url.split('/')[-1])
    if not os.path.exists(file_name.replace('.gz', '')):
        _fetch_and_unzip(remote_url, file_name)

    return os.path.join(dataset_path, 'cifar-100-binary')


def _download_voc(local_path):
    '''Download the dataset from http://host.robots.ox.ac.uk/pascal/VOC/voc2007/index.html.'''
    dataset_path = os.path.join(local_path, 'voc')
    if not os.path.exists(dataset_path):
        os.makedirs(dataset_path)

    print("************** Downloading the VOC2007 dataset **************")
    remote_url = "http://host.robots.ox.ac.uk/pascal/VOC/voc2007/VOCtrainval_06-Nov-2007.tar"
    file_name = os.path.join(dataset_path, remote_url.split('/')[-1])
    if not os.path.exists(os.path.join(dataset_path, 'VOCdevkit', 'VOC2007')):
        _fetch_and_unzip(remote_url, file_name)

    return os.path.join(dataset_path, 'VOCdevkit', 'VOC2007')


def _check_uncompressed_kaggle_display_advertising_files(dataset_path):
    """check uncompressed kaggle display advertising files."""
    file_name_list = ["train.txt", "test.txt", "readme.txt"]
    file_size_list = [11147184845, 1460246311, 1927]

    for file_name, file_size in zip(file_name_list, file_size_list):
        file_path = os.path.join(dataset_path, file_name)
        if not os.path.exists(file_path):
            return False
        else:
            if os.path.getsize(file_path) != file_size:
                print("************** {} may be error, need to download again **************".
                      format(file_path), flush=True)
                return False

    return True


def _download_kaggle_display_advertising(local_path):
    '''Download the dataset from http://go.criteo.net/criteo-research-kaggle-display-advertising-challenge-dataset.tar.gz.'''
    dataset_path = os.path.join(local_path, "kaggle_display_advertising")
    if not os.path.exists(dataset_path):
        os.makedirs(dataset_path)

    print("************** Downloading the Kaggle Display Advertising Challenge dataset **************")
    remote_url = "http://go.criteo.net/criteo-research-kaggle-display-advertising-challenge-dataset.tar.gz"
    file_name = os.path.join(dataset_path, remote_url.split('/')[-1])
    # already exist criteo-research-kaggle-display-advertising-challenge-dataset.tar.gz
    if os.path.exists(file_name):
        if os.path.getsize(file_name) == 4576820670:
            print("************** Uncompress already exists tar format data **************", flush=True)
            _unzip(file_name)
    if not _check_uncompressed_kaggle_display_advertising_files(dataset_path):
        _fetch_and_unzip_by_wget(remote_url, file_name)
    else:
        print("{} already have uncompressed kaggle display advertising dataset.".format(dataset_path), flush=True)

    return os.path.join(dataset_path)


download_checker = {
    'mnist': _download_mnist,
    'cifar10': _download_cifar10,
    'cifar100': _download_cifar100,
    'voc': _download_voc,
    'kaggle_display_advertising': _download_kaggle_display_advertising,
}


def download_dataset(dataset_name, local_path='.'):
    r'''
    This function is defined to easily download any public dataset
    without specifing much details.

    Args:
        dataset_name (str): The official name of dataset, currently supports `mnist`, `cifar10` and `cifar100`.
        local_path (str): Specifies the local location of dataset to be downloaded.
            Default: `.`.

    Returns:
        str, the source location of dataset downloaded.

    Examples:
        >>> from tinyms.data import download_dataset
        >>>
        >>> ds_path = download_dataset('mnist')
    '''
    download_func = download_checker.get(dataset_name)
    if download_func is None:
        print("Currently dataset_name only supports {}!".format(list(download_checker.keys())))
        sys.exit(0)

    return download_func(local_path)


def load_resized_img(path, width=256, height=256):
    """
    Load image with RGB and resize to (256, 256).

    Args:
        path (str): image path.
        width (int): image width, default: 256.
        height (int): image height, default: 256.

    Returns:
        PIL image class.
    """
    return Image.open(path).convert('RGB').resize((width, height))


def load_img(path):
    """
    Load image with RGB.

    Args:
        path (str): image path.

    Returns:
        PIL image class.
    """
    if path is None or not is_image(path):
        assert path, '%s is none or is not an image'
    return Image.open(path).convert('RGB')


def save_image(img, img_path):
    """
    Save a numpy image to the disk.

    Args:
        img (Union[numpy.ndarray, Tensor]): Image to save.
        img_path (str): The path of the image.
    """
    if isinstance(img, Tensor):
        # Decode a [1, C, H, W] Tensor to image numpy array.
        mean = 0.5 * 255
        std = 0.5 * 255
        img = (img.asnumpy()[0] * std + mean).astype(np.uint8).transpose((1, 2, 0))
    elif not isinstance(img, np.ndarray):
        raise ValueError("img should be Tensor or numpy array, but get {}".format(type(img)))
    img_pil = Image.fromarray(img)
    img_pil.save(img_path)
