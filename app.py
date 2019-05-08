import os
import math
from flask import Flask, request, jsonify
from flask_cors import CORS

from g2p import SequiturTool, Translator, loadG2PSample

app = Flask(__name__)
CORS(app)


class Options(dict):
    def __init__(self, modelFile="final.mdl", encoding="UTF-8",
                 variants_number=4, variants_mass=0.9):
        super(Options, self).__init__(modelFile=modelFile, encoding=encoding,
                                      variants_number=variants_number,
                                      variants_mass=variants_mass)

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            return None

    def __setattr__(self, name, value):
        self[name] = value


def pronounce(words):
    options = Options(
        modelFile=os.getenv("G2P_MODEL", "final.mdl")
    )
    translator = Translator(SequiturTool.procureModel(options, loadG2PSample))

    for word in words:
        left = tuple(word.lower())

        output = {
            "word": word,
            "results": []
        }
        try:
            total_posterior = 0.0
            n_variants = 0
            n_best = translator.nBestInit(left)
            while (total_posterior < options.variants_mass
                   and n_variants < options.variants_number):
                try:
                    log_like, result = translator.nBestNext(n_best)
                except StopIteration:
                    break
                posterior = math.exp(log_like - n_best.logLikTotal)
                output["results"].append(
                    {"posterior": posterior, "pronunciation": " ".join(result)}
                )
                total_posterior += posterior
                n_variants += 1
        except Translator.TranslationFailure:
            pass
        yield output


@app.route("/pron/<word>", methods=["GET", "OPTIONS"])
def route_pronounce(word):
    """Main entry point - Does the important stuff
    """
    return jsonify(list(pronounce([word]))), 200


@app.route("/pron", methods=["POST", "OPTIONS"])
def route_pronounce_many():
    content = request.get_json(force=True)
    if "words" not in content:
        return jsonify({"error": "Field 'words' missing."}), 400

    return jsonify(list(pronounce(content["words"]))), 200
