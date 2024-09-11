from __future__ import annotations

import gzip
import json
from glob import glob
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pytest
from monty.io import zopen

from pymatgen.core import SETTINGS, Molecule, Structure
from pymatgen.util.testing import TEST_FILES_DIR

if TYPE_CHECKING:
    from typing import Any

    from pymatgen.util.typing import PathLike


@pytest.fixture(autouse=True)
def _set_aims_species_dir_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIMS_SPECIES_DIR", f"{TEST_FILES_DIR}/io/aims/species_directory")


@pytest.fixture(autouse=True)
def _set_aims_species_dir_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setitem(SETTINGS, "AIMS_SPECIES_DIR", f"{TEST_FILES_DIR}/io/aims/species_directory")


def check_band(test_line: str, ref_line: str) -> bool:
    """Check if band lines are the same.

    Args:
        test_line (str): Line generated in the test file
        ref_line (str): Line generated for the reference file

    Returns:
        bool: True if all points in the test and ref lines are the same
    """
    test_pts = [float(inp) for inp in test_line.split()[-9:-2]]
    ref_pts = [float(inp) for inp in ref_line.split()[-9:-2]]

    return np.allclose(test_pts, ref_pts) and test_line.split()[-2:] == ref_line.split()[-2:]


def compare_files(test_name: str, work_dir: Path, ref_dir: Path) -> None:
    """Compare files generated by tests with ones in reference directories.

    Args:
        test_name (str): The name of the test (subdir for ref files in ref_dir)
        work_dir (Path): The directory to look for the test files in
        ref_dir (Path): The directory where all reference files are located

    Raises:
        AssertionError: If a line is not the same
    """
    for file in glob(f"{work_dir / test_name}/*in"):
        with open(file) as test_file:
            test_lines = [line.strip() for line in test_file if len(line.strip()) > 0 and line[0] != "#"]

        with gzip.open(f"{ref_dir / test_name / Path(file).name}.gz", "rt") as ref_file:
            ref_lines = [line.strip() for line in ref_file.readlines() if len(line.strip()) > 0 and line[0] != "#"]

        for test_line, ref_line in zip(test_lines, ref_lines, strict=True):
            if "output" in test_line and "band" in test_line:
                assert check_band(test_line, ref_line)
            else:
                assert test_line == ref_line

    with open(f"{ref_dir / test_name}/parameters.json") as ref_file:
        ref = json.load(ref_file)
    ref.pop("species_dir", None)
    ref_output = ref.pop("output", None)

    with open(f"{work_dir / test_name}/parameters.json") as check_file:
        check = json.load(check_file)

    check.pop("species_dir", None)
    check_output = check.pop("output", None)

    assert ref == check

    if check_output:
        for ref_out, check_out in zip(ref_output, check_output, strict=True):
            if "band" in check_out:
                assert check_band(check_out, ref_out)
            else:
                assert ref_out == check_out


def comp_system(
    structure: Structure,
    user_params: dict[str, Any],
    test_name: str,
    work_dir: Path,
    ref_dir: Path,
    generator_cls: type,
    properties: list[str] | None = None,
    prev_dir: str | None | Path = None,
    user_kpt_settings: dict[str, Any] | None = None,
) -> None:
    """Compare files generated by tests with ones in reference directories.

    Args:
        structure (Structure): The system to make the test files for
        user_params (dict[str, Any]): The parameters for the input files passed by the user
        test_name (str): The name of the test (subdir for ref files in ref_dir)
        work_dir (Path): The directory to look for the test files in
        ref_dir (Path): The directory where all reference files are located
        generator_cls (type): The class of the generator
        properties (list[str] | None): The list of properties to calculate
        prev_dir (str | Path | None): The previous directory to pull outputs from
        user_kpt_settings (dict[str, Any] | None): settings for k-point density in FHI-aims

    Raises:
        ValueError: If the input files are not the same
    """
    if user_kpt_settings is None:
        user_kpt_settings = {}

    k_point_density = user_params.pop("k_point_density", 20)

    try:
        generator = generator_cls(
            user_params=user_params,
            k_point_density=k_point_density,
            user_kpoints_settings=user_kpt_settings,
        )
    except TypeError:
        generator = generator_cls(user_params=user_params, user_kpoints_settings=user_kpt_settings)

    input_set = generator.get_input_set(structure, prev_dir, properties)
    input_set.write_input(work_dir / test_name)

    return compare_files(test_name, work_dir, ref_dir)


def compare_single_files(ref_file: PathLike, test_file: PathLike) -> None:
    """Compare single files generated by tests with ones in reference directories.

    Args:
        ref_file (PathLike): The reference file to compare against
        test_file (PathLike): The file to compare against the reference

    Raises:
        ValueError: If the files are not the same
    """
    with open(test_file) as tf:
        test_lines = tf.readlines()[5:]

    with zopen(f"{ref_file}.gz", mode="rt") as rf:
        ref_lines = rf.readlines()[5:]

    for test_line, ref_line in zip(test_lines, ref_lines, strict=True):
        if "species_dir" in ref_line:
            continue
        if test_line.strip() != ref_line.strip():
            raise ValueError(f"{test_line=} != {ref_line=}")


Si: Structure = Structure(
    lattice=((0.0, 2.715, 2.715), (2.715, 0.0, 2.715), (2.715, 2.715, 0.0)),
    species=("Si", "Si"),
    coords=((0, 0, 0), (0.25, 0.25, 0.25)),
)

O2: Molecule = Molecule(species=("O", "O"), coords=((0, 0, 0.622978), (0, 0, -0.622978)))
