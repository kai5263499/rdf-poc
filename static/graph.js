/*jshint browser:true, jquery:true*/
/*global jsnx:true, d3:true*/
var G;
(function() {
    "use strict";
    var startNodes = 5;
    G = new jsnx.MultiDiGraph();
    var passes = [
        "/graph/api/v1.0/nodesFor/",
        "/graph/api/v1.0/edgesFor/"
    ];

    var checkIsIPV4 = function(entry) {
      var blocks = entry.split(".");
      if(blocks.length === 4) {
        return blocks.every(function(block) {
          return parseInt(block,10) >=0 && parseInt(block,10) <= 255;
        });
      }
      return false;
    };

    var handleNodeClick = function(node) {
        console.log('clicked',node);
        if(node.node.match(/^http.*/i)) {
          return;
        }

        if(node.data.group === 2) {
          $.getJSON("/graph/api/v1.0/edgesFor/"+node.node).then(function(d) {addData(d, false);});
        } else {
          $.getJSON("/graph/api/v1.0/nodesFor/"+node.node).then(function(d) {addData(d, true);});
        }
    };

    var addData = function(data,loadEdges) {
      if(loadEdges === undefined || loadEdges === null) {
        loadEdges = false;
      }
      var loadEdgesFor = [];
      for(var n=0;n<data.graph.nodes.length;n++) {
          var d = data.graph.nodes[n];
          var id = d.label.replace(/\'/g,'');
          var group = 0;
          if(checkIsIPV4(id)) {
            group = 1;
          } else if(id.match(/^\d+$/)) {
            group = 2;
          } else if(id.match(/^http/i)) {
            group = 3;
          }
          G.addNode(id,{label:id, group:group});

          if(loadEdges && group === 2) {
            loadEdgesFor.push(id);
          }
      }

      if(loadEdgesFor.length > 0) {
        Promise.resolve($.post("/graph/api/v1.0/edgesForMultiple/",{"ids":loadEdgesFor.join(',')}, "json").then(function(d) {addData(d, false);}));
      }

      for(var p=0;p<data.graph.links.length;p++) {
          var e = data.graph.links[p];
          var source = data.graph.nodes[e.source].label.replace(/\'/g,'');
          var target = data.graph.nodes[e.target].label.replace(/\'/g,'');
          G.addEdge(source,target);
      }

      d3.selectAll('.node').on('click', handleNodeClick);

      // console.log('density:',jsnx.density(G));
      // console.log('degreeHistogram',jsnx.degreeHistogram(G));
    };

    var draw = function() {
        var color = d3.scale.category20();
        
        jsnx.draw(G, {element: '.graph',
                  height: document.documentElement.clientHeight,
                  width: document.documentElement.clientWidth,
                  withLabels: true,
                  labelStyle: {
                      'text-anchor': 'middle',
                      'dominant-baseline': 'hanging',
                      'cursor': 'pointer',
                      'fill': '#000'
                  },
                  layoutAttr: {
                    charge: -500,
                    gravity: 0.5
                  },
                  panZoom: {
                    enabled: true
                  },
                  nodeAttr: {
                    r: 10
                  },
                  nodeStyle: {
                    fill: function(d) {
                      return color(d.data.group || +d.node % 4);
                    },
                    stroke: 'none'
                  },
                  edgeStyle: {
                    fill: '#999'
                  }
        }, true);
    };

    Promise.resolve($.getJSON("/graph/api/v1.0/fileNodes/"+startNodes))
        .then(function( data ) {
            console.log('fileNodes',data);
            $('.spinner').remove();
            draw();
            addData(data, true);
            return data.graph.nodes;
        })
        .then(function(nodes) {
            console.log('l2 edges', nodes.length);

            var promises = [];
            var loadEdgesFor = [];
            R.map(function(n) {
                var id = n.label.replace(/\'/g,'');
                loadEdgesFor.push(id);
            }, nodes);

            if(loadEdgesFor.length > 0) {
              promises.push(Promise.resolve($.post("/graph/api/v1.0/edgesForMultiple/",{"ids":loadEdgesFor.join(',')}, "json").then(function(d) {addData(d, false);})));
            }

            return Promise.all(promises)
                .then(function(results) {
                    console.log('l2 is completely done');
                });
        });
}());
