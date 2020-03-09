import os
from copy import deepcopy
import math
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from webargs import fields
from flask_apispec import use_kwargs, marshal_with, FlaskApiSpec, doc
from marshmallow import validate, Schema
from apispec import APISpec, BasePlugin
from apispec.ext.marshmallow import MarshmallowPlugin
from typing import Dict, List
import re
from g2p import SequiturTool, Translator, loadG2PSample

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False
app.config["APISPEC_SWAGGER_URL"] = "/pron/swagger.json"
app.config["APISPEC_SWAGGER_UI_URL"] = "/pron/swagger-ui/"
CORS(app)


# See https://github.com/jmcarp/flask-apispec/issues/155#issuecomment-562542538
class DisableOptionsOperationPlugin(BasePlugin):
    def operation_helper(self, operations, **kwargs):
        # flask-apispec auto generates an options operation, which cannot handled by apispec.
        # apispec.exceptions.DuplicateParameterError: Duplicate parameter with name body and location body
        # => remove
        operations.pop("options", None)

app.config["APISPEC_SPEC"] = APISpec(
    title="Pronounce",
    version="0.0.1-alpha",
    openapi_version="2.0",
    plugins=[MarshmallowPlugin(), DisableOptionsOperationPlugin()],
)
docs = FlaskApiSpec(app)


class Options(dict):
    def __init__(self, modelFile="final.mdl", lexicon=None, encoding="UTF-8",
                 variants_number=4, variants_mass=0.9, models=None):
        super(Options, self).__init__(modelFile=modelFile, lexicon=lexicon,
                                      encoding=encoding,
                                      variants_number=variants_number,
                                      variants_mass=variants_mass,
                                      models=models)

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            return None

    def __setattr__(self, name, value):
        self[name] = value


def read_lexicon(lex_path: str) -> Dict[str, List[str]]:
    lexicon = dict()
    lex_has_probs = None
    with open(lex_path) as lex_f:
        for line in lex_f:
            fields = line.strip().split()
            # Probe first line for syntax
            if lex_has_probs is None:
                lex_has_probs = re.match('[0-1]\.[0-9]+', fields[1]) is not None
            word = fields[0]
            prob = 1.0
            if lex_has_probs:
                prob = fields[1]
                pron = fields[2:]
            else:
                pron = fields[1:]
            output = lexicon.get(word, {"results": [], "word": word})
            output["results"].append({
                "pronunciation": ' '.join(pron),
                "normalizedProb": prob,
                "manual": True,
            })
            lexicon[word] = output

    return lexicon

model_options = {
    "en-IS": Options(
        modelFile=os.getenv("G2P_MODEL_EN_IS", "en-IS.cmudict_frobv1.20200305.mdl"),
        lexicon=os.getenv("G2P_LEXICON_EN_IS", "en-IS.cmudict_frobv1.20200305.lex")
    ),
    "is-IS": Options(
        modelFile=os.getenv("G2P_MODEL_IS_IS", "is-IS.ipd_clean_slt2018.mdl"),
        lexicon=os.getenv("G2P_LEXICON_IS_IS", "is-IS.ipd_clean_slt2018.lex")
    ),
}

models = {
    lang: {
        "translator": Translator(SequiturTool.procureModel(model_options[lang],
                                                           loadG2PSample)),
        "lookup_lexicon": read_lexicon(
            model_options[lang].lexicon) if model_options[lang].lexicon else None
    } for lang in model_options
}

def pronounce(words, max_variants_number=4, variants_mass=0.9, language_code='is-IS'):
    translator = models[language_code]["translator"]
    lookup_lexicon = models[language_code]["lookup_lexicon"]
    for word in words:
        output = {
            "word": word,
            "results": []
        }

        if lookup_lexicon:
            output = deepcopy(lookup_lexicon.get(word.lower(), output))
            output["word"] = word

        left = tuple(word.lower())
        try:
            total_posterior = 0.0
            n_variants = 0
            n_best = translator.nBestInit(left)
            highest_posterior = 0.0
            while (total_posterior < variants_mass
                   and n_variants < max_variants_number):
                try:
                    log_like, result = translator.nBestNext(n_best)
                except StopIteration:
                    break
                posterior = math.exp(log_like - n_best.logLikTotal)
                if posterior > highest_posterior:
                    highest_posterior = posterior
                output["results"].append({
                    "normalizedProb": posterior / highest_posterior,
                    "posterior": posterior,
                    "pronunciation": " ".join(result),
                    "manual": False,
                })
                total_posterior += posterior
                n_variants += 1
        except Translator.TranslationFailure:
            pass
        yield output


def pron_to_tsv(prons):
    return "\n".join(
        "{w}\t{prob}\t{pron}".format(w=item["word"],
                                     prob=res["normalizedProb"],
                                     pron=res["pronunciation"])
        for item in prons
        for res in item["results"])



@app.route("/pron/<word>", methods=["GET"])
@doc(description="Output pronunciation for word")
@use_kwargs({
    "t": fields.Str(
        description="Output type. Valid values are `tsv` and `json`",
        example='json',
        validate=validate.OneOf(['json', 'tsv']),
    ),
    "max_variants_number": fields.Int(
        description="Maximum number of pronunciation variants generated with "
        "G2P. Default is 4",
        validate=validate.Range(min=0, max=20),
        example=4
    ),
    "total_variants_mass": fields.Float(
        description="Generate pronuncation variants with G2P until this "
        "probability mass or until number reaches `max_variants_number`",
        validate=validate.Range(min=0.0, max=1.0),
        example=0.9,
    ),
    "language_code": fields.Str(
        description="Language code for word",
        validate=validate.OneOf(models.keys()),
        missing='is-IS'
    ),
}, locations=["query"])
@marshal_with(None)
def route_pronounce(word, max_variants_number=4,
                    total_variants_mass=0.9, t='json', language_code='is-IS'):
    pron = pronounce(
        [word],
        max_variants_number=max_variants_number,
        variants_mass=total_variants_mass,
        language_code=language_code,
    )
    if t and t == "tsv":
        return Response(response=pron_to_tsv(pron),
                        content_type="text/tab-separated-values")

    return jsonify(list(pron))

docs.register(route_pronounce)


@app.route("/pron", methods=["POST", "OPTIONS"])
@doc(description="Output pronunciation list of words")
@use_kwargs({
    "words": fields.List(fields.Str(), example=["bandabrandur"]),
    "t": fields.Str(
        description="Output type. Valid values are `tsv` and `json`",
        example='json',
        validate=validate.OneOf(['json', 'tsv']),
    ),
    "max_variants_number": fields.Int(
        description="Maximum number of pronunciation variants generated with "
        "G2P. Default is 4",
        validate=validate.Range(min=0, max=20),
        example=4,
    ),
    "total_variants_mass": fields.Float(
        description="Generate pronuncation variants with G2P until this "
        "probability mass or until number reaches `max_variants_number`",
        validate=validate.Range(min=0.0, max=1.0),
        example=0.9
    ),
    "language_code": fields.Str(
        description="Language code for words",
        validate=validate.OneOf(models.keys()),
        missing='is-IS'
    ),
})
@marshal_with(None)
def route_pronounce_many(words, max_variants_number=4,
                         total_variants_mass=0.9, t='json', language_code='is-IS'):
    pron = pronounce(
        words,
        max_variants_number=max_variants_number,
        variants_mass=total_variants_mass,
        language_code=language_code
    )
    if t and t == "tsv":
        return Response(response=pron_to_tsv(pron),
                        status=200,
                        content_type="text/tab-separated-values")
    return jsonify(list(pron))

docs.register(route_pronounce_many)
