import argparse
import os
import numpy as np
import h5py
import OpenVisus as ov
import json

def find_largest_dataset(hdf5_file):
    largest_dataset = None
    largest_size = 0

    def visit_datasets(name, node):
        nonlocal largest_dataset, largest_size
        if isinstance(node, h5py.Dataset):
            size = np.product(node.shape)
            if size > largest_size:
                largest_dataset = name
                largest_size = size

    hdf5_file.visititems(visit_datasets)
    return largest_dataset

def collect_metadata(hdf5_file):
    metadata = {}

    def visit(name, node):
        if isinstance(node, h5py.Dataset) or isinstance(node, h5py.Group):
            node_attrs = {}
            for attr in node.attrs:
                if isinstance(node.attrs[attr], np.ndarray):
                    node_attrs[attr] = node.attrs[attr].tolist()
                else:
                    node_attrs[attr] = node.attrs[attr]
            metadata[name] = node_attrs

    hdf5_file.visititems(visit)
    return metadata


def convert_hdf5_to_idx(src_filename, idx_filename,input_dir):
    with h5py.File(src_filename, 'r') as f:
        dataset_path = find_largest_dataset(f)
        if not dataset_path:
            print(f"No dataset found in {src_filename}")
            return
        print(f'FINDING PATH `{dataset_path}`')
        dataset = f[dataset_path]
        if dataset.ndim == 2:
            D, H, W = 1, dataset.shape[0], dataset.shape[1]
            data = np.zeros((H, W), dtype=np.float32)  # Preallocate array for 2D dataset

            chunk_size = (50, 50)  # Define chunk size
            for y in range(0, H, chunk_size[1]):
                for x in range(0, W, chunk_size[0]):
                    chunk_dims = (
                        min(chunk_size[0], W - x),
                        min(chunk_size[1], H - y),
                    )
                    # Read the current chunk and assign it to the corresponding location in 'data'
                    data[y:y+chunk_dims[1], x:x+chunk_dims[0]] = dataset[y:y+chunk_dims[1], x:x+chunk_dims[0]]
            vmin, vmax = np.min(data), np.max(data)
            dims = [W, H]

        elif dataset.ndim == 3:
            D, H, W = dataset.shape
            data = np.zeros((D, H, W), dtype=np.float32)  # Preallocate array for 3D dataset

            chunk_size = (50, 50, 1)  # Define chunk size
            for z in range(0, D, chunk_size[2]):
                for y in range(0, H, chunk_size[1]):
                    for x in range(0, W, chunk_size[0]):
                        chunk_dims = (
                            min(chunk_size[0], W - x),
                            min(chunk_size[1], H - y),
                            min(chunk_size[2], D - z),
                        )
                        # Read the current chunk and assign it to the corresponding location in 'data'
                        data[z:z+chunk_dims[2], y:y+chunk_dims[1], x:x+chunk_dims[0]] = dataset[z:z+chunk_dims[2], y:y+chunk_dims[1], x:x+chunk_dims[0]]
            vmin, vmax = np.min(data), np.max(data)
            dims = [W, H, D]
        else:
            print("Dataset dimensionality is not supported.")
            return

        field = ov.Field.fromString(f"DATA {str(data.dtype)} format(row_major) min({vmin}) max({vmax})")

        # Create IDX dataset
        db = ov.CreateIdx(
            url=idx_filename,
            dims=dims,
            fields=[field],
            compression="raw")

        print(f"Dataset created with dimensions: {W}x{H}x{D}")
        db.write(data)
        print("Write complete; Compressing Now....")
        db.compressDataset(["zip"])
        print('Data Compressed and Ready!')
        metadata = collect_metadata(f)
        metadata_filename = os.path.join(input_dir, 'metadata.json')
        with open(metadata_filename, 'w') as json_file:
            json.dump(metadata, json_file, indent=4)
        print(f"All metadata written to {metadata_filename}")



def main():
    parser = argparse.ArgumentParser(description='Convert HDF5-based files to IDX format.')
    parser.add_argument('src_file_directory', type=str, help='directory containing HDF5-based files')
    args = parser.parse_args()

    input_dir = args.src_file_directory
    if not os.path.isdir(input_dir):
        print(f"The specified path {input_dir} is not a directory.")
        return

    visus_found = False

    # Check recursively if any folder named "visus" exists in input_dir or its subdirectories
    for root, dirs, files in os.walk(input_dir):
        if 'visus' in dirs:
            visus_found = True
            break

    # Supported HDF5-based file extensions
    hdf5_extensions = ('.nxs', '.h5', '.hdf5', '.hdf')
    for file in os.listdir(input_dir):
        if file.endswith(hdf5_extensions):
            if not visus_found:  #Don't do the conversion if this is already a hdf5 file that has visus IDX support (keep meta data in hdf5, all other data in idx)
                src_filename = os.path.join(input_dir, file)
                idx_filename = os.path.join(input_dir,  'visus.idx')
                print(f'Converting {src_filename} to {idx_filename}')
                convert_hdf5_to_idx(src_filename, idx_filename,input_dir)
            

if __name__ == "__main__":
    main()
    print('----> End of convert_hdf5_to_idx')