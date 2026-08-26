"""Asking the slicer what a part actually costs.

The mass in the build report is density times solid volume: an upper bound that
assumes the part is solid all the way through. A real print is walls and a
lattice, so that number is wrong by a factor that depends on the geometry — and
wrong in the direction that matters, because it is the number you would use to
decide whether a print is worth starting.

The slicer knows. It is also the only program that knows this version's
complete settings schema, so rather than writing a 3MF here and hoping, the
part is handed to it and it writes its own.

How far apart the two numbers are, on the parts in this tree: the dehydrator
collar estimates at 173 g of ASA by density and slices at 153 g at stock
settings — thirteen percent, all of it infill. Add the support and 5 mm brim
its README records as validated and it slices at 172 g, which lands back beside
the estimate by coincidence rather than by agreement: the support puts back
about what the infill saved. Both numbers move for different reasons, and a
figure quoted without the settings under it means nothing.

Nothing in this workspace has yet been printed *and weighed* — the masses in
the project READMEs are this same density estimate, so they cannot confirm
anything here. A kitchen scale under one finished print would turn all of this
from plausible into known, and is the cheapest open item in REFERENCE.md.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from cadkit import printer
from cadkit.export import EXPORTS

# Where the slicer is, in order of preference. Flatpak first because that is how
# both of these install on this machine, and `--command` is needed because the
# app id runs the GUI wrapper rather than the binary that has a CLI.
CANDIDATES = (
    ("flatpak", "run", "--command=orca-slicer", "com.orcaslicer.OrcaSlicer"),
    ("flatpak", "run", "--command=bambu-studio", "com.bambulab.BambuStudio"),
    ("orca-slicer",),
    ("bambu-studio",),
    ("OrcaSlicer",),
    ("BambuStudio",),
)

# Plate types the slicer knows, in the order worth trying. A filament supports
# a plate exactly when that plate's bed temperature is non-zero in its profile,
# which is how ASA rules out the cool plate without anything here knowing what
# ASA is. Textured PEI comes first because it is the one that suits everything.
PLATES = (
    ("textured_plate_temp", "Textured PEI Plate"),
    ("hot_plate_temp", "High Temp Plate"),
    ("eng_plate_temp", "Engineering Plate"),
    ("cool_plate_temp", "Cool Plate"),
    ("supertack_plate_temp", "Supertack Plate"),
)

# Both numbers share one line with the model-only printing time, so neither
# pattern can be anchored to the start of it. "Total estimated" is the one to
# report: it is what the printer's own display counts down from, because it
# includes the heating and the purge that the model-only figure leaves out.
TIME = re.compile(r"total estimated time:\s*([0-9dhms .]+)")
GRAMS = re.compile(r"filament used \[g\]\s*=\s*([0-9.]+)")
UNITS = {"d": 1440, "h": 60, "m": 1, "s": 1 / 60}


class SlicerError(RuntimeError):
    """The slicer is missing, or refused the job and said why."""


@dataclass(frozen=True)
class Slice:
    """What one trip through the slicer produced."""

    minutes: float
    grams: float
    layer_h: float
    walls: int
    infill: float
    gcode: Path
    settings: dict[str, str]  # what was overridden, and to what

    @property
    def duration(self) -> str:
        hours, minutes = divmod(round(self.minutes), 60)
        return f"{hours}h {minutes:02d}m" if hours else f"{minutes}m"

    def line(self) -> str:
        """The cost, with enough of the settings to read it in context.

        Support and brim are deliberately *not* here even though they are in
        `settings`: they change the number by more than anything else on this
        line and deserve a sentence of their own rather than a suffix in a
        parenthesis nobody finishes reading.
        """
        return (
            f"{self.duration}, {self.grams:.0f} g "
            f"({self.layer_h:.2f} mm layers, {self.walls} walls, "
            f"{self.infill:.0f}% infill)"
        )


@cache
def find_slicer() -> tuple[str, ...]:
    """The argv prefix that runs a slicer, or a message naming what to install."""
    for candidate in CANDIDATES:
        if candidate[0] == "flatpak":
            if not shutil.which("flatpak"):
                continue
            listed = subprocess.run(
                ["flatpak", "info", candidate[-1]],
                capture_output=True,
                text=True,
                check=False,
            )
            if listed.returncode == 0:
                return candidate
        elif shutil.which(candidate[0]):
            return candidate
    raise SlicerError(
        "no slicer found. Install one:\n"
        "  flatpak install flathub com.orcaslicer.OrcaSlicer\n"
        "  flatpak install flathub com.bambulab.BambuStudio"
    )


@cache
def profiles() -> Path:
    """The vendor profile tree for this printer's make.

    Found by walking the installed slicer's data directory rather than by a
    hard-coded path, so an upgrade that moves the files needs no change here.
    """
    roots = [
        Path("/var/lib/flatpak/app/com.orcaslicer.OrcaSlicer/current/active/files/share"),
        Path("/var/lib/flatpak/app/com.bambulab.BambuStudio/current/active/files/share"),
        Path("/usr/share"),
        Path("/usr/local/share"),
        Path.home() / ".local/share",
    ]
    for root in roots:
        for app in ("OrcaSlicer", "BambuStudio"):
            tree = root / app / "profiles" / printer.SLICER_VENDOR
            if (tree / "machine").is_dir():
                return tree
    raise SlicerError(
        f"found a slicer but not its {printer.SLICER_VENDOR} profiles. "
        f"Looked under: {', '.join(str(r) for r in roots)}"
    )


def flatten(kind: str, name: str, seen: tuple[str, ...] = ()) -> dict:
    """One profile with its whole `inherits` chain merged into it.

    The slicer's vendor profiles are a tree — a machine is four keys and a
    parent — and `--load-settings` wants a complete one. Deliberately keeps
    `from`, `instantiation` and `setting_id`: without them the slicer decides
    the process is not compatible with the printer and refuses the job, which
    is a long way from what the error message says.
    """
    if name in seen:
        raise SlicerError(f"{kind} profile {name!r} inherits from itself")
    path = profiles() / kind / f"{name}.json"
    if not path.is_file():
        raise SlicerError(f"no {kind} profile named {name!r} under {profiles()}")

    data = json.loads(path.read_text())
    parent = data.pop("inherits", None)
    if parent:
        base = flatten(kind, parent, (*seen, name))
        base.update(data)
        data = base
    data["name"] = name
    return data


def _for_machine(kind: str) -> list[dict]:
    """Every profile of a kind that names this machine as compatible."""
    machine = printer.SLICER_MACHINE
    out = []
    for path in sorted((profiles() / kind).glob("*.json")):
        try:
            head = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        if machine in head.get("compatible_printers", ()):
            out.append(head | {"name": path.stem})
    return out


def process_profile(layer_h: float) -> str:
    """The stock process profile for a layer height, by name.

    Chosen from what declares itself compatible with this machine rather than
    by constructing a filename: the naming convention is the slicer's and it
    changes, but the compatibility list is what the slicer itself reads.

    An exact height or nothing. Quietly slicing at 0.16 mm because 0.08 mm was
    not on the list would change the time, the finish and every number in the
    report, and the report would not say so.
    """
    candidates = _for_machine("process")
    if not candidates:
        raise SlicerError(
            f"no process profile is compatible with {printer.SLICER_MACHINE}"
        )

    heights: dict[float, list[str]] = {}
    for profile in candidates:
        match = re.match(r"([0-9.]+)mm", profile["name"])
        if match:
            heights.setdefault(float(match.group(1)), []).append(profile["name"])

    matched = heights.get(round(layer_h, 3))
    if not matched:
        offered = ", ".join(f"{h:g}" for h in sorted(heights))
        raise SlicerError(
            f"no {layer_h:g} mm process profile for {printer.SLICER_MACHINE}. "
            f"Available layer heights: {offered} mm"
        )
    # "Standard" where there is one; the alternatives are quality presets that
    # differ in more than the layer height they are named for.
    return next((n for n in sorted(matched) if "Standard" in n), sorted(matched)[0])


def filament_profile(material) -> str:
    """The vendor filament profile for a material, by its declared name."""
    if material is None or not material.filament:
        raise SlicerError(
            "the model declares no material, so there is nothing to weigh. "
            "Set MATERIAL in the model file, or pass --material."
        )
    wanted = material.filament
    for profile in _for_machine("filament"):
        if profile["name"].startswith(wanted + " @"):
            return profile["name"]
    raise SlicerError(
        f"no filament profile starting {wanted!r} is compatible with "
        f"{printer.SLICER_MACHINE}. Check Material.filament in cadkit/materials.py."
    )


def plate_for(filament: dict) -> str:
    """A build plate this filament will stick to.

    A profile gives a bed temperature per plate type and zeroes the ones the
    material must not go on — ASA has 0 for the cool plate and 100 for the
    textured one. Reading that is how this stays true for a filament nothing
    here has heard of.
    """
    for key, plate in PLATES:
        temps = filament.get(key) or ["0"]
        if float(temps[0]) > 0:
            return plate
    raise SlicerError(f"{filament['name']} names no build plate it can be printed on")


def tuned(findings=()) -> dict[str, str]:
    """Slicer settings a printability finding justifies changing. Currently one.

    A brim, when the part is one the warp or stability rules had something to
    say about — those are exactly the two failures a brim answers.

    Nothing else, on purpose. It is tempting to raise the wall count to this
    workspace's structural minimum or swap the infill pattern, but neither
    follows from a finding: they are decisions about the part, they change what
    the part *is*, and a report that quietly re-tunes what it is measuring is
    not measuring anything. The model decides; this only reacts to what the
    rules actually saw.
    """
    at_risk = {f.rule for f in findings if f.severity in ("fail", "warn")}
    if at_risk & {"warp_risk", "stability"}:
        return {"brim_type": "outer_only", "brim_width": "5"}
    return {}


def brim(width: float) -> dict[str, str]:
    """Slicer settings for a brim of a given width, inside and out.

    Inner as well as outer, because the parts here that need one are open
    collars: the inside of the ring is as much of a first-layer edge as the
    outside, and holding only the outside holds half of it.
    """
    return {"brim_type": "outer_and_inner", "brim_width": f"{width:g}"}


def _settings(material, layer_h, support, overrides):
    """The three flattened profiles, plus whatever is being overridden."""
    machine = flatten("machine", printer.SLICER_MACHINE)
    process = flatten("process", process_profile(layer_h))
    filament = flatten("filament", filament_profile(material))

    machine["curr_bed_type"] = plate_for(filament)
    if support:
        # "Everywhere", not build-plate-only: the dehydrator collar's seat ring
        # hangs inward over its own cavity, and build-plate-only leaves it in
        # mid-air. That part is the reason this default is what it is.
        process |= {
            "enable_support": "1",
            "support_type": "normal(auto)",
            "support_on_build_plate_only": "0",
        }
    process |= overrides
    return machine, process, filament


def _parse_time(text: str) -> float:
    """ "4h 8m 28s" as minutes."""
    total = 0.0
    for value, unit in re.findall(r"([0-9.]+)\s*([dhms])", text):
        total += float(value) * UNITS[unit]
    return total


def slice_stl(
    stl: Path,
    material,
    workdir: Path,
    layer_h: float = printer.LAYER_H,
    support: bool = False,
    findings=(),
    extra: dict[str, str] | None = None,
    export_3mf: str | None = None,
    timeout: int = 900,
) -> Slice:
    """Run the slicer over one STL and read back what it will cost.

    `workdir` has to be somewhere the slicer can see. Both Flatpaks hold
    `filesystems=home` and nothing more, so a directory under the repo works
    and one under /tmp silently does not — the sandbox reports a missing file
    rather than a permission error, which is a confusing hour if you have not
    met it before.
    """
    overrides = dict(tuned(findings))
    overrides.update(extra or {})
    machine, process, filament = _settings(material, layer_h, support, overrides)
    if support:
        overrides["support"] = "everywhere"

    workdir = Path(workdir)
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)
    for name, data in (
        ("machine.json", machine),
        ("process.json", process),
        ("filament.json", filament),
    ):
        (workdir / name).write_text(json.dumps(data, indent=1))

    argv = [
        *find_slicer(),
        "--load-settings",
        f"{workdir / 'machine.json'};{workdir / 'process.json'}",
        "--load-filaments",
        str(workdir / "filament.json"),
        "--slice",
        "0",
        "--arrange",
        "1",
        "--outputdir",
        str(workdir),
    ]
    if export_3mf:
        # A bare filename: the slicer joins this onto --outputdir, so an
        # absolute path here becomes outputdir + path and the export fails.
        argv += ["--export-3mf", export_3mf]
    argv.append(str(Path(stl).resolve()))

    try:
        # cwd is the scratch directory because the slicer writes a debug log
        # and a copy of result.json wherever it is started from, and starting
        # it from the repo root leaves both at the top of the tree.
        run = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=os.environ,
            cwd=workdir,
        )
    except subprocess.TimeoutExpired as expired:
        raise SlicerError(f"the slicer did not finish within {timeout}s") from expired

    result = workdir / "result.json"
    if result.is_file():
        reported = json.loads(result.read_text())
        if reported.get("return_code", 0) != 0:
            raise SlicerError(
                f"{reported.get('error_string', 'the slicer refused the job')} "
                f"(code {reported['return_code']})"
            )
    elif run.returncode != 0:
        detail = (run.stderr or run.stdout or "").strip().splitlines()
        raise SlicerError(
            "the slicer failed and wrote no result: "
            + (detail[-1] if detail else f"exit {run.returncode}")
        )

    gcode = next(iter(sorted(workdir.glob("*.gcode"))), None)
    if gcode is None:
        raise SlicerError("the slicer reported success but wrote no G-code")
    text = gcode.read_text(errors="replace")

    grams = GRAMS.search(text)
    minutes = TIME.search(text)
    if grams is None or minutes is None:
        # Refusing to guess. A wrong gram figure is worse than none, because
        # only one of the two gets checked against reality.
        raise SlicerError(f"{gcode.name} carries no time or weight in its header")

    return Slice(
        minutes=_parse_time(minutes.group(1)),
        grams=float(grams.group(1)),
        layer_h=float(reported.get("layer_height", layer_h)),
        walls=int(reported.get("wall_loops", 0)),
        infill=float(reported.get("sparse_infill_density", 0.0)),
        gcode=gcode,
        settings=overrides,
    )


def workdir_for(project: str, name: str) -> Path:
    """Where a model's slicer scratch files go.

    Under `exports/`, which is gitignored in full, and under the repo, which is
    the only place the Flatpak sandbox can reach.
    """
    return EXPORTS / ".slice" / project / name
