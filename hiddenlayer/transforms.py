import re
from .graph import Node
from . import ge



###########################################################################
# Transforms
###########################################################################

class Fold():
    def __init__(self, pattern, op, name=None):
        # TODO: validation op and name are valid
        self.pattern = ge.GEParser(pattern).parse()
        self.op = op
        self.name = name

    def apply(self, graph):
        while True:
            matches, _ = graph.search(self.pattern)
            if not matches:
                break

            # Replace pattern with new node
            if self.op == "__first__":
                combo = matches[0]
            else:
                combo = Node(uid=graph.sequence_id(matches),
                                name=self.name or " &gt; ".join([l.title for l in matches]),
                                op=self.op or self.pattern,
                                output_shape=matches[-1].output_shape)
                combo._caption = "/".join(filter(None, [l.caption for l in matches]))
            graph.replace(matches, combo)


class Prune():
    def __init__(self, pattern):
        self.pattern = ge.GEParser(pattern).parse()

    def apply(self, graph):
        while True:
            matches, _ = graph.search(self.pattern)
            if not matches:
                break
            # Remove found nodes
            graph.remove(matches)


class FoldDuplicates():
    def apply(self, graph):
        matches = True
        while matches:
            for node in graph.nodes.values():
                pattern = ge.SerialPattern([ge.NodePattern(node.op), ge.NodePattern(node.op)])
                matches, _ = pattern.match(graph, node)
                if matches:
                    combo = Node(uid=graph.sequence_id(matches),
                                name=node.name,
                                op=node.op,
                                output_shape=node.output_shape)
                    combo._caption = node.caption
                    combo.repeat = sum([n.repeat for n in matches])
                    graph.replace(matches, combo)
                    break


class Rename():
    def __init__(self, op=None, name=None, to=None):
        assert op or name, "Either op or name must be provided"
        assert not(op and name), "Either op or name should be provided, but not both"
        assert bool(to), "The to parameter is required" 
        self.to = to
        self.op = re.compile(op) if op else None
        self.name = re.compile(name) if name else None
    
    def apply(self, graph):
        for node in graph.nodes.values():
            if self.op:
                node.op = self.op.sub(self.to, node.op)
            # TODO: name is not tested yet
            if self.name:
                node.name = self.name.sub(self.to, node.name)


# Transforms to simplify graphs by folding layers that tend to be 
# used together often, such as Conv/BN/Relu.
# These transforms are used AFTER the framework specific transforms
# that map TF and PyTorch graphs to a common representation.
SIMPLICITY_TRANSFORMS = [
    Fold("Conv > Conv > BatchNormalization > Relu", "ConvConvBnRelu"),
    Fold("Conv > BatchNormalization > Relu", "ConvBnRelu"),
    Fold("Conv > BatchNormalization", "ConvBn"),
    Fold("Conv > Relu", "ConvRelu"),
    Fold("Linear > Relu", "LinearRelu"),
    Fold("ConvBnRelu > MaxPool", "ConvBnReluMaxpool"),
    Fold("ConvRelu > MaxPool", "ConvReluMaxpool"),
    FoldDuplicates(),
]