"""Read official ZIP evidence and match it to individual movement rows.

XML contents are evidence, not a cryptographic signature validation. Matching
requires tracking, exact cents, date (±1), and compatible account/bank evidence.
ZIP members are never extracted using their supplied paths.
"""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from io import BytesIO
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET

from cep.catalog import account_identifier, bank_code, identifier
from cep.columns import CEP_COLUMNS
from cep.queries import CepQuery, amount
from utils.statement_dates import full_date, text_key


XML_FIELDS = {
    "beneficiary_name": ("nombrebeneficiario", "nombeneficiario", "nombrebene", "beneficiario.nombre", "beneficiario.nombrecompleto", "datosbeneficiario.nombre"),
    "sender_name": ("nombreordenante", "nomordenante", "ordenante.nombre", "ordenante.nombrecompleto", "datosordenante.nombre"),
    "beneficiary_rfc": ("rfcbeneficiario", "beneficiario.rfc", "beneficiario.curp", "datosbeneficiario.rfc"),
    "sender_rfc": ("rfcordenante", "ordenante.rfc", "ordenante.curp", "datosordenante.rfc"),
    "destination": ("cuentabeneficiaria", "clabebeneficiaria", "cuentabene", "beneficiario.cuenta", "beneficiario.clabe"),
    "origin": ("cuentaordenante", "clabeordenante", "ordenante.cuenta", "ordenante.clabe"),
    "tracking": ("claverastreo", "clavederastreo", "rastreo", "numerorastreo"),
    "reference": ("referencianumerica", "numeroreferencia", "referencia"),
    "date": ("fechaoperacion", "fechapago", "fechadeoperacion", "fechatransferencia"),
    "amount": ("montopago", "montooperacion", "importepago", "datospago.monto", "datospago.importe", "monto", "importe"),
    "concept": ("conceptopago", "conceptodelpago", "concepto"),
    "issuer": ("institucionemisora", "institucionordenante", "ordenante.bancoemisor", "ordenante.banco", "bancoemisor", "bancoordenante"),
    "receiver": ("institucionreceptora", "beneficiario.bancoreceptor", "beneficiario.banco", "bancoreceptor", "bancobeneficiario"),
}
MAX_MEMBER = 12 * 1024 * 1024
MAX_TOTAL = 300 * 1024 * 1024
MAX_FILES = 6000


def _key(value):
    return re.sub(r"[^a-z0-9]", "", text_key(str(value).rsplit("}", 1)[-1]).lower())


def parse_cep_xml(content: bytes) -> dict[str, str]:
    if len(content) > MAX_MEMBER or re.search(br"<!\s*(?:DOCTYPE|ENTITY)\b", content, re.I):
        raise ValueError("XML excesivo o con declaraciones no permitidas")
    root = ET.fromstring(content)
    values = defaultdict(list)
    pending = [(root, "", 0)]
    while pending:
        node, parent, depth = pending.pop()
        if depth > 60:
            raise ValueError("XML con anidamiento excesivo")
        label = _key(node.tag)
        path = parent + "." + label if parent else label
        if node.text and node.text.strip() and not len(node):
            text = " ".join(node.text.split())
            values[label].append(text)
            values[path].append(text)
        for key, value in node.attrib.items():
            key = _key(key)
            text = " ".join(value.split())
            values[key].append(text)
            values[path + "." + key].append(text)
            values[label + "." + key].append(text)
        pending.extend((child, path, depth + 1) for child in reversed(node))
    result = {}
    for field_name, aliases in XML_FIELDS.items():
        found = []
        for alias in aliases:
            hits = values.get(alias, [])
            if not hits:
                hits = [v for key, vs in values.items() if key.endswith("." + alias) for v in vs]
            if hits:
                found = list(dict.fromkeys(hits))
                break
        if len(found) > 1:
            raise ValueError(f"XML con valores contradictorios para {field_name}")
        result[field_name] = found[0] if found else ""
    if not result["tracking"] or not full_date(result["date"]) or not amount(result["amount"]):
        raise ValueError("XML sin rastreo, fecha o monto CEP válidos")
    return result


def safe_name(value: str, size=45):
    value = re.sub(r"[^A-Z0-9._-]+", "_", text_key(value)).strip("._")
    return value[:size] or "SIN_DATO"


@dataclass
class CepRecord:
    data: dict[str, str]
    xml: bytes
    pdf: bytes | None
    source: str
    source_member: str
    xml_path: str = ""
    pdf_path: str = ""

    @property
    def signature(self):
        return hashlib.sha256(json.dumps(self.data, sort_keys=True).encode("utf-8")).hexdigest()


@dataclass
class CepEvidence:
    records: list[CepRecord] = field(default_factory=list)
    preserved: dict[str, bytes] = field(default_factory=dict)
    review: list[dict] = field(default_factory=list)
    summaries: list[str] = field(default_factory=list)

    def add_zip(self, source: str | Path | bytes, *, name="banxico.zip"):
        content = source if isinstance(source, bytes) else Path(source).read_bytes()
        if not isinstance(source, bytes):
            name = Path(source).name
        tag = safe_name(Path(name).stem, 30) + "_" + hashlib.sha256(content).hexdigest()[:10]
        prefix = "BANXICO_ORIGINAL/" + tag + "/"
        if any(key.startswith(prefix) for key in self.preserved):
            return
        with zipfile.ZipFile(BytesIO(content)) as archive:
            members = [i for i in archive.infolist() if not i.is_dir()]
            total = sum(len(v) for v in self.preserved.values()) + sum(i.file_size for i in members)
            if len(members) > MAX_FILES or total > MAX_TOTAL or any(i.file_size > MAX_MEMBER for i in members):
                raise ValueError("El ZIP excede los límites de tamaño para procesar CEP")
            payloads = {}
            for index, member in enumerate(members, 1):
                if member.flag_bits & 1:
                    raise ValueError("El ZIP está cifrado")
                # Numbered basenames cannot escape the final archive or collide.
                basename = safe_name(PurePosixPath(member.filename.replace("\\", "/")).name, 100)
                data = archive.read(member)
                if len(data) != member.file_size:
                    raise ValueError("Tamaño inconsistente en el ZIP")
                self.preserved[prefix + f"{index:04d}_" + basename] = data
                payloads[index] = (member.filename.replace("\\", "/"), data)
            pdfs = {i: (p, b) for i, (p, b) in payloads.items() if p.lower().endswith(".pdf")}
            xmls = {i: (p, b) for i, (p, b) in payloads.items() if p.lower().endswith(".xml")}
            used = set()
            known = {r.signature for r in self.records}
            for index, (path, data) in xmls.items():
                try:
                    fields = parse_cep_xml(data)
                except (ValueError, ET.ParseError) as error:
                    self.review.append({"Archivo": name + "/" + path, "Detalle": str(error)})
                    continue
                stem = str(PurePosixPath(path).with_suffix("")).casefold()
                options = [i for i, (p, b) in pdfs.items()
                           if str(PurePosixPath(p).with_suffix("")).casefold() == stem]
                if not options:
                    options = [i for i, (p, b) in pdfs.items()
                               if PurePosixPath(p).stem.casefold() == PurePosixPath(path).stem.casefold()]
                if not options and len(xmls) == len(pdfs) == 1:
                    options = list(pdfs)
                pdf = None
                if len(options) == 1 and options[0] not in used:
                    i = options[0]
                    if pdfs[i][1].lstrip().startswith(b"%PDF-"):
                        pdf = pdfs[i][1]
                        used.add(i)
                record = CepRecord(fields, data, pdf, name, path)
                if record.signature in known:
                    previous = next(r for r in self.records if r.signature == record.signature)
                    if previous.pdf is None and pdf:
                        previous.pdf = pdf
                    continue
                known.add(record.signature)
                self.records.append(record)
            for index, (path, data) in pdfs.items():
                if index not in used:
                    self.review.append({"Archivo": name + "/" + path, "Detalle": "PDF sin XML asociado inequívocamente"})
            for path, data in payloads.values():
                if PurePosixPath(path).name.casefold() == "resumen.txt":
                    self.summaries.extend(data.decode("utf-8-sig", "replace").splitlines())
        self._paths()

    def _paths(self):
        for record in self.records:
            d = record.data
            base = (full_date(d["date"]).isoformat() + "__BEN_" + safe_name(d["beneficiary_name"], 35)
                    + "__ORD_" + safe_name(d["sender_name"], 35) + "__" + safe_name(d["amount"], 20)
                    + "__" + safe_name(d["tracking"], 35) + "_" + record.signature[:8])
            record.xml_path = "XML/" + base + ".xml"
            record.pdf_path = "PDF/" + base + ".pdf" if record.pdf else ""


def _compatible(query: CepQuery, record: CepRecord):
    d = record.data
    if query.tracking.upper() != identifier(d["tracking"]).upper():
        return False
    if not query.operation_date or query.value is None:
        return False
    if abs((full_date(d["date"]) - query.operation_date).days) > 1 or amount(d["amount"]) != query.value:
        return False
    # When a field is known in the statement it must agree. Missing official
    # account/bank fields do not satisfy an expected value.
    for expected, actual in ((query.issuer, d["issuer"]), (query.receiver, d["receiver"])):
        if expected and bank_code(actual) != expected:
            return False
    destination = account_identifier(d["destination"])
    origin = account_identifier(d["origin"])
    if query.destination_aliases and destination not in query.destination_aliases:
        return False
    if query.direction == "ENVIADO" and query.owner_aliases and origin not in query.owner_aliases:
        return False
    if query.origin_aliases and origin not in query.origin_aliases:
        return False
    # At least one account anchors the link to this statement, even when its
    # TXT could not be generated because another field was missing.
    return bool(query.destination_aliases or (query.direction == "ENVIADO" and query.owner_aliases))


def match_evidence(queries: list[CepQuery], evidence: CepEvidence) -> dict[int, dict]:
    by_tracking = defaultdict(list)
    for record in evidence.records:
        by_tracking[identifier(record.data["tracking"]).upper()].append(record)
    options = {}
    for query in queries:
        compatible = [r for r in by_tracking.get(query.tracking.upper(), []) if _compatible(query, r)]
        exact = [r for r in compatible if full_date(r.data["date"]) == query.operation_date]
        options[query.row] = exact or compatible
    # An XML must not be assigned to two different same-direction operations.
    # When exact and ±1 dates compete, first reserve the exact-date evidence.
    exact_claims = {r.signature for q in queries for r in options[q.row]
                    if full_date(r.data["date"]) == q.operation_date}
    for query in queries:
        options[query.row] = [r for r in options[query.row]
                              if r.signature not in exact_claims or full_date(r.data["date"]) == query.operation_date]
    claims = defaultdict(list)
    for query in queries:
        if len(options[query.row]) == 1:
            claims[options[query.row][0].signature].append(query)
    output = {}
    for query in queries:
        result = dict.fromkeys(CEP_COLUMNS, "")
        result["CEP Tiene PDF"] = "NO"
        result["CEP Estado"] = "NO_APARECE_EN_ZIP" if query.candidate else "SIN_INDICIOS_SPEI"
        result["CEP Detalle"] = "; ".join(query.issues)
        candidates = by_tracking.get(query.tracking.upper(), [])
        matches = options[query.row]
        competing = bool(len(matches) == 1 and sum(
            q.direction == query.direction for q in claims[matches[0].signature]) > 1)
        if competing:
            result["CEP Estado"] = "REVISAR"
            result["CEP Detalle"] = "El mismo XML corresponde a varias filas indistinguibles; revisar duplicados"
            output[query.row] = result
            continue
        if len(matches) == 1:
            record = matches[0]
            d = record.data
            delta = (full_date(d["date"]) - query.operation_date).days
            result.update({
                "CEP Estado": "EXITO_FECHA_ALTERNATIVA" if delta else "EXITO",
                "CEP Detalle": "XML cotejado; fecha alternativa" if delta else "XML cotejado con el movimiento",
                "CEP Fecha": full_date(d["date"]), "CEP Diferencia Días": delta,
                "CEP Monto": float(amount(d["amount"])), "CEP Clave de Rastreo": d["tracking"],
                "CEP Referencia": d["reference"], "CEP Banco Emisor": d["issuer"],
                "CEP Banco Receptor": d["receiver"], "CEP Nombre Ordenante": d["sender_name"],
                "CEP RFC Ordenante": d["sender_rfc"], "CEP Cuenta Ordenante": d["origin"],
                "CEP Nombre Beneficiario": d["beneficiary_name"], "CEP RFC Beneficiario": d["beneficiary_rfc"],
                "CEP Cuenta Beneficiaria": d["destination"], "CEP Concepto": d["concept"],
                "CEP Tiene PDF": "SÍ" if record.pdf else "NO", "CEP Archivo PDF": record.pdf_path,
                "CEP Archivo XML": record.xml_path,
            })
        elif candidates:
            result["CEP Estado"] = "REVISAR"
            result["CEP Detalle"] = ("Varios XML compatibles; no se asigna uno automáticamente" if len(matches) > 1
                                     else "Existe rastreo, pero fecha, importe, cuenta o banco no concuerdan")
        elif query.candidate and not query.ready:
            result["CEP Estado"] = "NO_CONSULTABLE"
        # Summary negatives never override a successfully matched XML. Without
        # all six structured fields, they remain unassigned review evidence.
        if result["CEP Estado"] == "NO_APARECE_EN_ZIP":
            for line in evidence.summaries:
                if "NO SE PUDO LOCALIZAR" not in text_key(line):
                    continue
                fields = [v.strip() for v in line.split(",")]
                if len(fields) < 7:
                    continue
                if (identifier(fields[1]).upper() == query.tracking.upper()
                        and full_date(fields[0]) and abs((full_date(fields[0]) - query.operation_date).days) <= 1
                        and bank_code(fields[2]) == query.issuer and bank_code(fields[3]) == query.receiver
                        and account_identifier(fields[4]) in query.destination_aliases and amount(fields[5]) == query.value):
                    result["CEP Estado"] = "FALLO_BUSQUEDA_CEP"
                    result["CEP Detalle"] = line[:500]
                    break
        output[query.row] = result
    return output
