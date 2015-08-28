#!flask/bin/python
from flask import Flask, jsonify, redirect, send_from_directory, request
from rdflib import plugin
from rdflib.store import Store
from rdflib.store import NO_STORE
from rdflib.store import VALID_STORE
from rdflib.graph import ConjunctiveGraph as Graph
import networkx as nx
from networkx.readwrite import json_graph
from rdflib import Literal
import time
import os
import json
import random

app = Flask(__name__, static_url_path='/static')

DBURI = Literal("mysql+mysqldb://username:password@hostname:3306/database")


def getStore():
    store = plugin.get("SQLAlchemy", Store)()

    rt = store.open(DBURI, create=True)
    if rt == NO_STORE:
        store.open(DBURI, create=True)
    else:
        assert rt == VALID_STORE, "There underlying store is corrupted"

    return store


def addRootNodesToGraph(sg, qres):
    for row in qres:
        # print row
        if row[0][:1] != '#':
            continue
        label = row[0][1:]
        sg.add_node(label, label=label)


def addResultsToGraph(sg, sourceId, qres):
    for row in qres:
        if row[0][:1] != '#':
            continue
        label = row[0][1:]

        sg.add_node(label, label=label)
        sg.add_edge(sourceId, label, .5)
        # print row


def get_edgesgraphfor(sourceId, sg, g):
    start_time = time.time()

    query = '''SELECT ?edge {
      ?link rgml:source ns1:%s .
      ?link rgml:target ?edge
    }
    ORDER BY RAND()
    LIMIT 10''' % (sourceId)
    # print "sparql: %s" % query
    qres = g.query(query)

    query_duration = time.time() - start_time

    sg.add_node(sourceId, label=sourceId)
    addResultsToGraph(sg, sourceId, qres)
    return {'sg': sg, 'query_duration': query_duration, 'qres': qres}


@app.route('/')
def root():
    return redirect("/static/index.html", code=302)


@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)


@app.route('/graph/api/v1.0/edgesForMultiple/', methods=['POST'])
def get_edgesForMultiple():
    ids = request.form['ids'].split(',')

    g = Graph(store=getStore())
    sg = nx.MultiDiGraph()
    duration = 0
    qres_len = 0
    for id in ids:
        r = get_edgesgraphfor(id, sg, g)
        duration = duration + r['query_duration']
        qres_len = qres_len + len(r['qres'])

    return jsonify({'edges': qres_len, 'duration': duration, 'graph': json_graph.node_link_data(sg)})


@app.route('/graph/api/v1.0/edgesFor/<string:sourceId>', methods=['GET'])
def get_edgesFor(sourceId):
    sg = nx.MultiDiGraph()
    g = Graph(store=getStore())
    r = get_edgesgraphfor(sourceId, sg, g)

    return jsonify({'edges': len(r['qres']), 'duration': r['query_duration'], 'graph': json_graph.node_link_data(sg)})


@app.route('/graph/api/v1.0/nodesFor/<string:sourceId>', methods=['GET'])
def get_nodesFor(sourceId):
    start_time = time.time()
    g = Graph(store=getStore())
    sg = nx.MultiDiGraph()

    query = '''SELECT ?node {
  {
    ?link rgml:target ns1:%s .
    ?link rgml:source ?node
  } UNION {
    ?link rgml:target <%s> .
    ?link rgml:source ?node
  }
}
ORDER BY RAND()
LIMIT 10''' % (sourceId, '#\'%s\'' % sourceId)
    # print "sparql: %s" % query
    qres = g.query(query)
    query_duration = time.time() - start_time

    sg.add_node(sourceId, label=sourceId)
    addResultsToGraph(sg, sourceId, qres)

    return jsonify({'edges': len(qres), 'duration': query_duration, 'graph': json_graph.node_link_data(sg)})


@app.route('/graph/api/v1.0/fileNodes/<int:limit>', methods=['GET'])
def get_rootNodes(limit):
    start_time = time.time()
    with open('rootnodes.json') as data_file:
        data = json.load(data_file)
        node_sample = [data['nodes'][i] for i in sorted(random.sample(xrange(len(data['nodes'])), limit))]
        data['nodes'] = node_sample
        query_duration = time.time() - start_time

        return jsonify({'roots': limit, 'duration': query_duration, 'graph': data})


# This is to build a root node cache. For some reason this operation is very expensive
@app.route('/graph/api/v1.0/generateRootNodes/<int:limit>', methods=['GET'])
def generate_rootNodes(limit):
    start_time = time.time()
    g = Graph(store=getStore())
    sg = nx.MultiDiGraph()

    query = '''SELECT DISTINCT ?node {
  ?link rgml:source ?node
}
ORDER BY RAND()
LIMIT %d''' % (limit)
    qres = g.query(query)

    query_duration = time.time() - start_time

    addRootNodesToGraph(sg, qres)

    with open('rootnodes.json', 'w') as outfile:
        json.dump(json_graph.node_link_data(sg), outfile)

    return jsonify({'roots': limit, 'duration': query_duration, 'graph': json_graph.node_link_data(sg)})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8181))
    app.run(host='0.0.0.0', port=port, debug=True)
