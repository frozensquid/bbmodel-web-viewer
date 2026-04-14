#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import math
import re
import struct
import sys
from pathlib import Path
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from pygltflib import (
        ARRAY_BUFFER,
        ELEMENT_ARRAY_BUFFER,
        FLOAT,
        UNSIGNED_SHORT,
        GLTF2,
        SCALAR,
        TRIANGLES,
        VEC2,
        VEC3,
        Accessor,
        Asset,
        Buffer,
        BufferView,
        Image,
        Material,
        Mesh,
        Node,
        PbrMetallicRoughness,
        Primitive,
        Sampler,
        Scene,
        Texture,
        TextureInfo,
    )
except Exception as exc:
    print("pygltflib est requis. Installe-le avec : pip install pygltflib", file=sys.stderr)
    print(f"Détail: {exc}", file=sys.stderr)
    raise SystemExit(1)

# Sampler filters / wrap modes (constants glTF)
NEAREST = 9728
LINEAR = 9729
REPEAT = 10497

# Indices « Blockbench » des 8 sommets (comme getGlobalVertexPositions / three_custom.js).
# Notre coin 0=(x1,y1,z1) … 6=(x2,y2,z2) avec from=(x1,y1,z1), to=(x2,y2,z2).
BB_VERTEX_TO_OUR_CORNER = [6, 2, 5, 1, 3, 7, 0, 4]

# Ordre des 4 sommets par face = BufferGeometry.setShape() (js/util/three_custom.js),
# pas getVertexIndices() — c’est cet ordre qui reçoit arr[0..3] dans updateUV.
_FACE_SHAPE_BB_ORDER: Dict[str, List[int]] = {
    "east": [0, 1, 2, 3],
    "west": [4, 5, 6, 7],
    "up": [4, 1, 5, 0],
    "down": [7, 2, 6, 3],
    "south": [5, 0, 7, 2],
    "north": [1, 4, 3, 6],
}

FACE_VERTEX_ORDER = {
    face: [BB_VERTEX_TO_OUR_CORNER[i] for i in bb]
    for face, bb in _FACE_SHAPE_BB_ORDER.items()
}

FACE_NORMALS = {
    "north": (0.0, 0.0, -1.0),
    "south": (0.0, 0.0, 1.0),
    "east": (1.0, 0.0, 0.0),
    "west": (-1.0, 0.0, 0.0),
    "up": (0.0, 1.0, 0.0),
    "down": (0.0, -1.0, 0.0),
}

# Même ordre que Canvas.face_order / setShape (east → … → north).
FACE_KEYS = ("east", "west", "up", "down", "south", "north")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convertit un .bbmodel Blockbench en .glb/.gltf")
    parser.add_argument("input_file", help="Chemin vers le .bbmodel")
    parser.add_argument("--output", help="Chemin du fichier de sortie (.glb ou .gltf)")
    parser.add_argument("--scale", type=float, default=1.0 / 16.0, help="Echelle Minecraft -> glTF (défaut: 1/16)")
    parser.add_argument("--texture-name", default=None, help="Nom du PNG exporté en mode .gltf")
    parser.add_argument("--linear", action="store_true", help="Utilise un filtrage linéaire au lieu de nearest")
    return parser.parse_args()


def deg_to_rad(x: float) -> float:
    return x * math.pi / 180.0


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def align4(data: bytearray) -> None:
    while len(data) % 4 != 0:
        data.append(0)


def sanitize_name(name: str) -> str:
    name = re.sub(r"[^\w\-. ]+", "_", name).strip()
    return name or "unnamed"


def parse_data_uri(uri: str) -> Optional[Tuple[str, bytes]]:
    if not uri.startswith("data:"):
        return None
    header, b64 = uri.split(",", 1)
    mime = header.split(";")[0][5:]
    return mime, base64.b64decode(b64)


def detect_image_size(payload: bytes, mime: Optional[str] = None) -> Optional[Tuple[int, int]]:
    if len(payload) >= 24 and payload[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", payload[16:24])
        if w > 0 and h > 0:
            return int(w), int(h)
    if (mime == "image/jpeg") or (len(payload) >= 4 and payload[:2] == b"\xFF\xD8"):
        i = 2
        while i + 9 < len(payload):
            if payload[i] != 0xFF:
                i += 1
                continue
            marker = payload[i + 1]
            i += 2
            if marker in (0xD8, 0xD9):
                continue
            if i + 1 >= len(payload):
                break
            seg_len = (payload[i] << 8) | payload[i + 1]
            if seg_len < 2 or i + seg_len > len(payload):
                break
            if marker in (
                0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF,
            ) and seg_len >= 7:
                h = (payload[i + 3] << 8) | payload[i + 4]
                w = (payload[i + 5] << 8) | payload[i + 6]
                if w > 0 and h > 0:
                    return int(w), int(h)
                break
            i += seg_len
    return None


def to_vec3(v: Any, default: Tuple[float, float, float] = (0.0, 0.0, 0.0)) -> Tuple[float, float, float]:
    if isinstance(v, list) and len(v) == 3:
        return float(v[0]), float(v[1]), float(v[2])
    return default


def rotate_vec_xyz(v: Tuple[float, float, float], rotation_deg: Tuple[float, float, float]) -> Tuple[float, float, float]:
    x, y, z = v
    rx, ry, rz = [deg_to_rad(a) for a in rotation_deg]

    # X
    cy = math.cos(rx)
    sy = math.sin(rx)
    y, z = y * cy - z * sy, y * sy + z * cy

    # Y
    cy = math.cos(ry)
    sy = math.sin(ry)
    x, z = x * cy + z * sy, -x * sy + z * cy

    # Z
    cz = math.cos(rz)
    sz = math.sin(rz)
    x, y = x * cz - y * sz, x * sz + y * cz

    return x, y, z


def quaternion_from_euler_xyz_deg(rotation_deg: Iterable[float]) -> List[float]:
    x_deg, y_deg, z_deg = list(rotation_deg)
    x = deg_to_rad(x_deg)
    y = deg_to_rad(y_deg)
    z = deg_to_rad(z_deg)

    cx = math.cos(x / 2.0)
    sx = math.sin(x / 2.0)
    cy = math.cos(y / 2.0)
    sy = math.sin(y / 2.0)
    cz = math.cos(z / 2.0)
    sz = math.sin(z / 2.0)

    qw = cx * cy * cz - sx * sy * sz
    qx = sx * cy * cz + cx * sy * sz
    qy = cx * sy * cz - sx * cy * sz
    qz = cx * cy * sz + sx * sy * cz
    return [qx, qy, qz, qw]


def blockbench_face_uv_slots_pixel(uv_rect: List[float]) -> List[Tuple[float, float]]:
    """
    Les 4 UV (pixel) dans l’ordre Blockbench avant rotation — voir preview_controller.updateUV
    (arr[0]..[3] à partir de uv[0],uv[1],uv[2],uv[3]).
    """
    u0, v0, u1, v1 = (float(uv_rect[0]), float(uv_rect[1]), float(uv_rect[2]), float(uv_rect[3]))
    return [
        (u0, v0),
        (u1, v0),
        (u0, v1),
        (u1, v1),
    ]


def pixel_uv_to_gltf(u: float, v: float, tex_w: float, tex_h: float) -> Tuple[float, float]:
    # glTF spec: UV (0,0) = top-left, V increases downward (same as pixel coords).
    # Viewers load textures with flipY=false → V maps directly.
    return (u / tex_w, v / tex_h)


def rotate_uv_quad_blockbench(uvs4: List[Tuple[float, float]], rotation_deg: int) -> List[Tuple[float, float]]:
    """Même permutation que la boucle `while (rot > 0)` dans updateUV (Blockbench)."""
    arr = list(uvs4)
    rot = int(round(float(rotation_deg or 0))) % 360
    while rot > 0:
        a = arr[0]
        arr[0] = arr[2]
        arr[2] = arr[3]
        arr[3] = arr[1]
        arr[1] = a
        rot -= 90
    return arr


class BufferBuilder:
    def __init__(self) -> None:
        self.data = bytearray()

    def add_floats(self, values: List[float]) -> Tuple[int, int]:
        align4(self.data)
        offset = len(self.data)
        payload = struct.pack("<" + "f" * len(values), *values)
        self.data.extend(payload)
        return offset, len(payload)

    def add_u16(self, values: List[int]) -> Tuple[int, int]:
        align4(self.data)
        offset = len(self.data)
        payload = struct.pack("<" + "H" * len(values), *values)
        self.data.extend(payload)
        return offset, len(payload)

    def add_bytes(self, payload: bytes) -> Tuple[int, int]:
        align4(self.data)
        offset = len(self.data)
        self.data.extend(payload)
        return offset, len(payload)

    def blob(self) -> bytes:
        return bytes(self.data)

    def write(self, path: Path) -> None:
        ensure_parent_dir(path)
        path.write_bytes(self.blob())


def compute_min_max(values: List[float], stride: int) -> Tuple[List[float], List[float]]:
    chunks = [values[i:i + stride] for i in range(0, len(values), stride)]
    mins = [min(c[i] for c in chunks) for i in range(stride)]
    maxs = [max(c[i] for c in chunks) for i in range(stride)]
    return mins, maxs


def read_primary_texture(data: Dict[str, Any], input_path: Path) -> Tuple[Optional[str], Optional[bytes], Optional[str]]:
    textures = data.get("textures")
    if not isinstance(textures, list) or not textures:
        return None, None, None

    tex = textures[0]
    if not isinstance(tex, dict):
        return None, None, None

    name = tex.get("name") if isinstance(tex.get("name"), str) else "texture.png"
    suffix = Path(name).suffix or ".png"
    safe_name = sanitize_name(Path(name).stem) + suffix

    # Fichier à côté du .bbmodel (ex. cavalier.png) — prioritaire pour éviter base64 obsolète.
    for sidecar in (
        input_path.parent / Path(name).name,
        input_path.parent / f"{Path(name).stem}.png",
        input_path.parent / f"{Path(name).stem}.jpg",
    ):
        if sidecar.is_file():
            mime = "image/png" if sidecar.suffix.lower() == ".png" else "image/jpeg"
            return safe_name, sidecar.read_bytes(), mime

    source = tex.get("source")
    if isinstance(source, str):
        parsed = parse_data_uri(source)
        if parsed is not None:
            mime, payload = parsed
            return safe_name, payload, mime

    for key in ("relative_path", "path"):
        candidate_raw = tex.get(key)
        if not isinstance(candidate_raw, str) or not candidate_raw:
            continue
        candidate = Path(candidate_raw)
        if not candidate.is_absolute():
            candidate = (input_path.parent / candidate).resolve()
        if candidate.exists():
            mime = "image/png" if candidate.suffix.lower() == ".png" else "image/octet-stream"
            payload = candidate.read_bytes()
            return safe_name, payload, mime

    return None, None, None


def collect_groups(outliner: List[Any]) -> List[Tuple[Dict[str, Any], Optional[str]]]:
    result: List[Tuple[Dict[str, Any], Optional[str]]] = []

    def walk(node: Any, parent_uuid: Optional[str]) -> None:
        if not isinstance(node, dict):
            return
        result.append((node, parent_uuid))
        node_uuid = node.get("uuid") if isinstance(node.get("uuid"), str) else parent_uuid
        for child in node.get("children", []):
            if isinstance(child, dict):
                walk(child, node_uuid)

    for item in outliner:
        if isinstance(item, dict):
            walk(item, None)

    return result


def collect_direct_cube_uuids(group: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for child in group.get("children", []):
        if isinstance(child, str):
            out.append(child)
    return out


def cube_is_exportable(cube: Dict[str, Any]) -> bool:
    if cube.get("export") is False:
        return False
    if cube.get("visibility") is False:
        return False
    name = cube.get("name")
    if isinstance(name, str) and re.search(r"hitbox|collision|_hb\b", name, re.I):
        return False
    return True


def group_needs_gltf_node(group: Dict[str, Any], elements_by_uuid: Dict[str, Dict[str, Any]]) -> bool:
    """True si ce groupe ou un sous-groupe (dict) porte au moins un cube exportable."""
    for cube_uuid in collect_direct_cube_uuids(group):
        el = elements_by_uuid.get(cube_uuid)
        if el and el.get("type") == "cube" and cube_is_exportable(el):
            return True
    for child in group.get("children", []):
        if isinstance(child, dict) and group_needs_gltf_node(child, elements_by_uuid):
            return True
    return False


def build_cube_geometry_relative_to_group(
    cube: Dict[str, Any],
    group_origin: Tuple[float, float, float],
    sample_w: float,
    sample_h: float,
    scale: float,
) -> Tuple[List[float], List[float], List[float], List[int]]:
    from_v = to_vec3(cube.get("from"))
    to_v = to_vec3(cube.get("to"))
    cube_origin = to_vec3(cube.get("origin"), group_origin)
    cube_rotation = to_vec3(cube.get("rotation"))

    # Use from/to AS-IS (like Blockbench setShape) — do NOT sort/canonicalize,
    # because face vertex order in FACE_VERTEX_ORDER depends on from=x1,to=x2.
    x1, y1, z1 = from_v
    x2, y2, z2 = to_v

    corners = [
        (x1, y1, z1),
        (x2, y1, z1),
        (x2, y2, z1),
        (x1, y2, z1),
        (x1, y1, z2),
        (x2, y1, z2),
        (x2, y2, z2),
        (x1, y2, z2),
    ]

    transformed: List[Tuple[float, float, float]] = []
    for px, py, pz in corners:
        lx, ly, lz = px - cube_origin[0], py - cube_origin[1], pz - cube_origin[2]
        if cube_rotation != (0.0, 0.0, 0.0):
            lx, ly, lz = rotate_vec_xyz((lx, ly, lz), cube_rotation)
        # local to group node space
        gx = (cube_origin[0] + lx - group_origin[0]) * scale
        gy = (cube_origin[1] + ly - group_origin[1]) * scale
        gz = (cube_origin[2] + lz - group_origin[2]) * scale
        transformed.append((gx, gy, gz))

    positions: List[float] = []
    normals: List[float] = []
    uvs: List[float] = []
    indices: List[int] = []
    vert_cursor = 0

    faces = cube.get("faces", {}) if isinstance(cube.get("faces"), dict) else {}

    for face_name in FACE_KEYS:
        face = faces.get(face_name)
        if not isinstance(face, dict):
            continue

        # Blockbench: faces with texture === null are not rendered (updateFaces)
        face_tex = face.get("texture")
        if face_tex is None or face_tex is False:
            continue

        uv_rect = face.get("uv")
        if not isinstance(uv_rect, list) or len(uv_rect) != 4:
            continue

        corner_ids = FACE_VERTEX_ORDER[face_name]
        slots_px = blockbench_face_uv_slots_pixel(uv_rect)
        face_uvs = [pixel_uv_to_gltf(u, v, sample_w, sample_h) for u, v in slots_px]
        face_uvs = rotate_uv_quad_blockbench(face_uvs, int(round(float(face.get("rotation", 0) or 0))))

        nx, ny, nz = FACE_NORMALS[face_name]
        if cube_rotation != (0.0, 0.0, 0.0):
            nx, ny, nz = rotate_vec_xyz((nx, ny, nz), cube_rotation)

        for local_idx, corner_id in enumerate(corner_ids):
            px, py, pz = transformed[corner_id]
            positions.extend([px, py, pz])
            normals.extend([nx, ny, nz])
            uu, vv = face_uvs[local_idx]
            uvs.extend([uu, vv])

        # Même découpe que Cube.preview_controller.updateFaces (0,2,1) + (2,3,1)
        indices.extend([
            vert_cursor + 0, vert_cursor + 2, vert_cursor + 1,
            vert_cursor + 2, vert_cursor + 3, vert_cursor + 1,
        ])
        vert_cursor += 4

    return positions, normals, uvs, indices


def add_accessor_triplet(
    gltf: GLTF2,
    buffer_builder: BufferBuilder,
    positions: List[float],
    normals: List[float],
    uvs: List[float],
    indices: List[int],
) -> Tuple[int, int, int, int]:
    pos_off, pos_len = buffer_builder.add_floats(positions)
    nrm_off, nrm_len = buffer_builder.add_floats(normals)
    uv_off, uv_len = buffer_builder.add_floats(uvs)
    idx_off, idx_len = buffer_builder.add_u16(indices)

    pos_bv = len(gltf.bufferViews)
    gltf.bufferViews.append(BufferView(buffer=0, byteOffset=pos_off, byteLength=pos_len, target=ARRAY_BUFFER))

    nrm_bv = len(gltf.bufferViews)
    gltf.bufferViews.append(BufferView(buffer=0, byteOffset=nrm_off, byteLength=nrm_len, target=ARRAY_BUFFER))

    uv_bv = len(gltf.bufferViews)
    gltf.bufferViews.append(BufferView(buffer=0, byteOffset=uv_off, byteLength=uv_len, target=ARRAY_BUFFER))

    idx_bv = len(gltf.bufferViews)
    gltf.bufferViews.append(BufferView(buffer=0, byteOffset=idx_off, byteLength=idx_len, target=ELEMENT_ARRAY_BUFFER))

    pos_min, pos_max = compute_min_max(positions, 3)

    pos_acc = len(gltf.accessors)
    gltf.accessors.append(Accessor(bufferView=pos_bv, componentType=FLOAT, count=len(positions) // 3, type=VEC3, min=pos_min, max=pos_max))

    nrm_acc = len(gltf.accessors)
    gltf.accessors.append(Accessor(bufferView=nrm_bv, componentType=FLOAT, count=len(normals) // 3, type=VEC3))

    uv_acc = len(gltf.accessors)
    gltf.accessors.append(Accessor(bufferView=uv_bv, componentType=FLOAT, count=len(uvs) // 2, type=VEC2))

    idx_acc = len(gltf.accessors)
    gltf.accessors.append(Accessor(bufferView=idx_bv, componentType=UNSIGNED_SHORT, count=len(indices), type=SCALAR))

    return pos_acc, nrm_acc, uv_acc, idx_acc




def to_plain_json(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, list):
        return [to_plain_json(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_plain_json(v) for k, v in obj.items() if v is not None}
    if is_dataclass(obj):
        return {k: to_plain_json(v) for k, v in asdict(obj).items() if v is not None}
    if hasattr(obj, "to_dict"):
        try:
            return to_plain_json(obj.to_dict())
        except Exception:
            pass
    if hasattr(obj, "__dict__"):
        return {
            k: to_plain_json(v)
            for k, v in vars(obj).items()
            if not k.startswith("_") and v is not None
        }
    return obj


def sanitize_gltf_json_dict(data: Any) -> Any:
    """
    Supprime les champs que pygltflib émet vides mais que le validateur Khronos rejette
    (extensionsUsed=[], min/max=[], children=[], weights=[], etc.).
    """
    if isinstance(data, dict):
        out: Dict[str, Any] = {}
        for k, v in data.items():
            if v is None:
                continue
            v2 = sanitize_gltf_json_dict(v)
            if v2 is None:
                continue
            if v2 == []:
                continue
            if v2 == {}:
                continue
            out[k] = v2
        return out
    if isinstance(data, list):
        return [sanitize_gltf_json_dict(x) for x in data]
    return data


def save_glb_manual(gltf: GLTF2, binary_blob: bytes, output_path: Path) -> None:
    if hasattr(gltf, "to_dict"):
        try:
            json_dict = sanitize_gltf_json_dict(to_plain_json(gltf.to_dict()))
        except Exception:
            json_dict = sanitize_gltf_json_dict(to_plain_json(gltf))
    elif hasattr(gltf, "to_json"):
        json_dict = sanitize_gltf_json_dict(to_plain_json(json.loads(gltf.to_json())))
    else:
        json_dict = sanitize_gltf_json_dict(to_plain_json(gltf))

    json_bytes = json.dumps(json_dict, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    while len(json_bytes) % 4 != 0:
        json_bytes += b" "

    bin_bytes = binary_blob
    while len(bin_bytes) % 4 != 0:
        bin_bytes += b"\x00"

    total_length = 12 + 8 + len(json_bytes) + 8 + len(bin_bytes)
    header = struct.pack("<4sII", b"glTF", 2, total_length)
    json_chunk = struct.pack("<I4s", len(json_bytes), b"JSON") + json_bytes
    bin_chunk = struct.pack("<I4s", len(bin_bytes), b"BIN\x00") + bin_bytes

    ensure_parent_dir(output_path)
    output_path.write_bytes(header + json_chunk + bin_chunk)


def build_model(data: Dict[str, Any], input_path: Path, output_path: Path, scale: float, linear_filter: bool, texture_name_override: Optional[str]) -> Tuple[Path, Optional[Path]]:
    resolution = data.get("resolution", {})
    res_w = float(resolution.get("width", 16))
    res_h = float(resolution.get("height", 16))

    elements_by_uuid: Dict[str, Dict[str, Any]] = {}
    for element in data.get("elements", []):
        if isinstance(element, dict) and isinstance(element.get("uuid"), str):
            elements_by_uuid[element["uuid"]] = element

    groups = collect_groups(data.get("outliner", []))
    output_is_glb = output_path.suffix.lower() == ".glb"

    buffer_builder = BufferBuilder()
    gltf = GLTF2(asset=Asset(version="2.0", generator="bbmodel_to_gltf_fixed.py"))
    gltf.scene = 0
    gltf.scenes = [Scene(nodes=[])]
    gltf.nodes = []
    gltf.meshes = []
    gltf.buffers = []
    gltf.bufferViews = []
    gltf.accessors = []
    gltf.images = []
    gltf.textures = []
    gltf.samplers = []
    gltf.materials = []

    tex_name, tex_bytes, tex_mime = read_primary_texture(data, input_path)
    texture_written_path: Optional[Path] = None

    # Échantillonnage glTF = image réelle ; les UV du .bbmodel sont en pixels dans la grille projet
    # (souvent = resolution), placée en haut-gauche du PNG. Diviser par la hauteur/largeur du fichier
    # évite de mapper la face sur toute la hauteur d’un PNG 64×128 alors que la grille ne fait que 64.
    img_dims = detect_image_size(tex_bytes, tex_mime) if tex_bytes else None
    sample_w = float(img_dims[0]) if img_dims else res_w
    sample_h = float(img_dims[1]) if img_dims else res_h
    if sample_w <= 0:
        sample_w = res_w
    if sample_h <= 0:
        sample_h = res_h

    if texture_name_override:
        ext = Path(texture_name_override).suffix or (Path(tex_name).suffix if tex_name else ".png")
        tex_name = sanitize_name(Path(texture_name_override).stem) + ext

    # Pas de mipmaps dans l’image : NEAREST_MIPMAP_* / LINEAR_MIPMAP_* provoquent souvent des
    # artefacts (faces grises, noires ou délavées) dans les viewers WebGL / three.js.
    sampler = Sampler(
        magFilter=LINEAR if linear_filter else NEAREST,
        minFilter=LINEAR if linear_filter else NEAREST,
        wrapS=REPEAT,
        wrapT=REPEAT,
    )
    gltf.samplers.append(sampler)

    material_index = 0
    if tex_bytes:
        if output_is_glb:
            img_off, img_len = buffer_builder.add_bytes(tex_bytes)
            img_bv = len(gltf.bufferViews)
            gltf.bufferViews.append(BufferView(buffer=0, byteOffset=img_off, byteLength=img_len))
            gltf.images.append(Image(bufferView=img_bv, mimeType=tex_mime or "image/png", name=tex_name or "texture"))
        else:
            file_name = tex_name or "texture.png"
            texture_written_path = output_path.parent / file_name
            ensure_parent_dir(texture_written_path)
            texture_written_path.write_bytes(tex_bytes)
            gltf.images.append(Image(uri=file_name, name=Path(file_name).stem))

        gltf.textures.append(Texture(source=0, sampler=0))
        gltf.materials.append(
            Material(
                name="bbmodel_material",
                doubleSided=True,
                alphaMode="MASK",
                alphaCutoff=0.5,
                pbrMetallicRoughness=PbrMetallicRoughness(
                    baseColorTexture=TextureInfo(index=0),
                    metallicFactor=0.0,
                    roughnessFactor=1.0,
                ),
            )
        )
    else:
        gltf.materials.append(
            Material(
                name="bbmodel_material",
                doubleSided=True,
                pbrMetallicRoughness=PbrMetallicRoughness(metallicFactor=0.0, roughnessFactor=1.0),
            )
        )

    node_index_by_group_uuid: Dict[str, int] = {}
    group_origin_by_uuid: Dict[str, Tuple[float, float, float]] = {}

    for group, parent_uuid in groups:
        if not group_needs_gltf_node(group, elements_by_uuid):
            continue
        group_uuid = group.get("uuid") if isinstance(group.get("uuid"), str) else None
        group_origin = to_vec3(group.get("origin"))
        parent_origin = group_origin_by_uuid.get(parent_uuid, (0.0, 0.0, 0.0))
        local_translation = [
            (group_origin[0] - parent_origin[0]) * scale,
            (group_origin[1] - parent_origin[1]) * scale,
            (group_origin[2] - parent_origin[2]) * scale,
        ]

        node = Node(name=str(group.get("name", "group")), translation=local_translation)

        rotation = to_vec3(group.get("rotation"))
        if rotation != (0.0, 0.0, 0.0):
            node.rotation = quaternion_from_euler_xyz_deg(rotation)

        mesh_positions: List[float] = []
        mesh_normals: List[float] = []
        mesh_uvs: List[float] = []
        mesh_indices: List[int] = []
        vert_offset = 0

        for cube_uuid in collect_direct_cube_uuids(group):
            cube = elements_by_uuid.get(cube_uuid)
            if not cube or cube.get("type") != "cube" or not cube_is_exportable(cube):
                continue
            positions, normals, uvs, indices = build_cube_geometry_relative_to_group(
                cube, group_origin, sample_w, sample_h, scale
            )
            if not positions:
                continue
            mesh_positions.extend(positions)
            mesh_normals.extend(normals)
            mesh_uvs.extend(uvs)
            mesh_indices.extend([i + vert_offset for i in indices])
            vert_offset += len(positions) // 3

        if mesh_positions:
            pos_acc, nrm_acc, uv_acc, idx_acc = add_accessor_triplet(gltf, buffer_builder, mesh_positions, mesh_normals, mesh_uvs, mesh_indices)
            mesh_index = len(gltf.meshes)
            gltf.meshes.append(
                Mesh(
                    name=f"{node.name}_mesh",
                    primitives=[Primitive(attributes={"POSITION": pos_acc, "NORMAL": nrm_acc, "TEXCOORD_0": uv_acc}, indices=idx_acc, material=material_index, mode=TRIANGLES)],
                )
            )
            node.mesh = mesh_index

        node_index = len(gltf.nodes)
        gltf.nodes.append(node)
        if group_uuid:
            node_index_by_group_uuid[group_uuid] = node_index
            group_origin_by_uuid[group_uuid] = group_origin

    for group, parent_uuid in groups:
        group_uuid = group.get("uuid") if isinstance(group.get("uuid"), str) else None
        if not group_uuid or group_uuid not in node_index_by_group_uuid:
            continue
        node_index = node_index_by_group_uuid[group_uuid]
        if parent_uuid and parent_uuid in node_index_by_group_uuid:
            parent_node = gltf.nodes[node_index_by_group_uuid[parent_uuid]]
            if parent_node.children is None:
                parent_node.children = []
            parent_node.children.append(node_index)
        else:
            gltf.scenes[0].nodes.append(node_index)

    buffer_len = len(buffer_builder.data)
    if output_is_glb:
        gltf.buffers.append(Buffer(byteLength=buffer_len))
        save_glb_manual(gltf, buffer_builder.blob(), output_path)
    else:
        bin_name = output_path.with_suffix('.bin').name
        gltf.buffers.append(Buffer(byteLength=buffer_len, uri=bin_name))
        buffer_builder.write(output_path.with_suffix('.bin'))
        ensure_parent_dir(output_path)
        gltf.save(str(output_path))

    return output_path, texture_written_path


def main() -> int:
    args = parse_args()
    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"Fichier introuvable: {input_path}", file=sys.stderr)
        return 1

    output_path = Path(args.output) if args.output else input_path.with_suffix('.glb')

    try:
        data = json.loads(input_path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as exc:
        print(f"JSON invalide: {exc}", file=sys.stderr)
        return 1

    try:
        out_path, tex_path = build_model(data, input_path, output_path, args.scale, args.linear, args.texture_name)
    except Exception as exc:
        print(f"Erreur lors de la conversion: {exc}", file=sys.stderr)
        raise

    print("Conversion terminée.")
    print(f"Entrée : {input_path}")
    print(f"Sortie : {out_path}")
    if out_path.suffix.lower() == '.gltf':
        print(f"BIN    : {out_path.with_suffix('.bin')}")
    if tex_path:
        print(f"Texture: {tex_path}")
    else:
        print("Texture: embarquée ou absente")
    print("Note: cette version gère mieux la hiérarchie des bones/groupes et les cubes relatifs au parent.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
