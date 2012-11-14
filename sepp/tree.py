"""SATe - Phylogenetic Tree Container, effectively a wrapper of dendropy.Tree"""

# This file is part of SATe

# SATe is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Jiaye Yu and Mark Holder, University of Kansas

# This file is copied to SEPP and is used as an external library

import copy
from dendropy import Tree, Taxon
from dendropy import Edge
from dendropy import Node
from dendropy import DataSet as Dataset
from dendropy import convert_node_to_root_polytomy
from sepp import get_logger

_LOG = get_logger(__name__)

class PhylogeneticTree(object):
    """Data structure to store phylogenetic tree, wrapping dendropy.Tree."""
    def __init__(self, dendropy_tree):
        self._tree = dendropy_tree
        self.n_leaves = self.count_leaves()
        self._tree.seed_node.edge.tail_node = None
        self._tree.seed_node.edge.length = None

    def get_tree(self):
        return self._tree
    den_tree = property(get_tree)
    
    def count_leaves(self):
        return len(self._tree.leaf_nodes())

    def count_nodes(self):
        return len(self._tree.nodes())

    def calc_splits(self):
        n = self.count_leaves()
        for i in self._tree.postorder_edge_iter():
            nd = i.head_node
            if nd.is_leaf():
                i.num_leaves_below = 1
            else:
                i.num_leaves_below = sum([j.edge.num_leaves_below for j in nd.child_nodes()])

    def get_centroid_edge(self):
        """Get centroid edge"""
        root = self._tree.seed_node
        root_children = root.child_nodes()
        if root_children and (not hasattr(root_children[0].edge, "num_leaves_below")):
            self.calc_splits()
            n_leaves = self.count_leaves()
        else:
            if root.edge:
                n_leaves = root.edge.num_leaves_below
            else:
                n_leaves = sum([j.edge.num_leaves_below for j in root_children])
        centroid_edge = None
        centroid_imbalance = n_leaves
        half_taxa = n_leaves/2
        for edge in self._tree.postorder_edge_iter():
            if edge.tail_node is None:
                continue
            n_descendants = edge.num_leaves_below
            imbalance = abs(half_taxa - n_descendants)
            if (imbalance < centroid_imbalance):
                centroid_edge = edge
                centroid_imbalance = imbalance
            assert centroid_edge is not None
        return centroid_edge

    def get_longest_internal_edge(self):
        longest_internal_edge = None
        longest_len = -1.0
        for edge in self._tree.postorder_edge_iter():
            if edge.tail_node is None:
                continue
            if (edge.length is not None) and edge.is_internal() and edge.length > longest_len:
                longest_internal_edge = edge
                longest_len = edge.length
        assert longest_internal_edge is not None
        return longest_internal_edge

    def get_longest_edge(self):
        longest_edge = None
        longest_len = -1.0
        for edge in self._tree.postorder_edge_iter():
            if edge.tail_node is None:
                continue
            if edge.length is not None and edge.length > longest_len:
                longest_edge = edge
                longest_len = edge.length
        assert longest_edge is not None
        return longest_edge

    def get_adjacent_edges(self, e):
        he = [i for i in e.head_node.get_incident_edges() if i is not e]
        te = [i for i in e.tail_node.get_incident_edges() if i is not e]
        he.extend(te)
        return he

    def get_breaking_edge(self, option):
        if option.lower() == 'centroid':
            return self.get_centroid_edge()
        elif option.lower() == 'longest':
            return self.get_longest_edge()
        else:
            raise ValueError('Unknown break strategy "%s"' % option)

    def bipartition_by_edge(self, e):
        """Prunes the subtree that attached to the head_node of edge e and returns them as a separate tree."""

        t = self._tree
        nr = e.head_node
        assert e.tail_node is not None
        assert e.head_node is not None
        assert nr.parent_node is e.tail_node
        is_valid_tree(t)

        n = self.n_leaves
        potentially_deleted_nd = e.tail_node
        grandparent_nd = potentially_deleted_nd.parent_node
        e.tail_node.remove_child(nr, suppress_deg_two=True)

        nr.edge.length = None
        nr.parent_node = None
        convert_node_to_root_polytomy(nr)
        t1 = PhylogeneticTree(Tree(seed_node=nr))
        n1 = t1.n_leaves # temp we could speed this up, by telling the Phylogenetic tree how many leaves it has

        if hasattr(e, "num_leaves_below"):
            if grandparent_nd is None:
                old_root = potentially_deleted_nd
                if old_root.edge:
                    old_root.edge.num_leaves_below -= n1
            else:
                if potentially_deleted_nd in grandparent_nd.child_nodes():
                    potentially_deleted_nd.edge.num_leaves_below -= n1
                old_root = grandparent_nd
                if old_root.edge:
                    old_root.edge.num_leaves_below -= n1
                while old_root.parent_node:
                    old_root = old_root.parent_node
                    if old_root.edge:
                        old_root.edge.num_leaves_below -= n1
        else:
            old_root = grandparent_nd or potentially_deleted_nd
            while old_root.parent_node:
                old_root = old_root.parent_node

        t2 = PhylogeneticTree(Tree(seed_node=old_root))

        is_valid_tree(t1._tree)
        is_valid_tree(t2._tree)
        return t1, t2

    def leaf_node_names(self):
        leaves = self._tree.leaf_nodes()
        return [i.taxon.label for i in leaves]

    def compose_newick(self):
        return self._tree.compose_newick()

    def write_newick_to_path(self, path):
        tree_handle = open(path, "w")
        tree_handle.write(self.compose_newick())
        tree_handle.write(";\n")
        tree_handle.close()
        
    def read_tree_from_file(self, treefile, file_format):
        dataset = Dataset()
        dataset.read(open(treefile, 'rU'), schema=file_format)
        dendropy_tree = dataset.trees_blocks[0][0]
        self._tree = dendropy_tree
        self.n_leaves = self.count_leaves()
        
        
    def get_subtree(self, taxa):
        if len(taxa) == 0:
            return None
        tree = Tree(self._tree)        
        if isinstance(taxa[0],str):
            tree.prune_taxa_with_labels(taxa)
        elif isinstance(taxa[0],Taxon):
            tree.prune_taxa(taxa)
        return PhylogeneticTree(tree)
    
    def bisect_tree(self, breaking_edge_style='centroid'):
        """Partition 'tree' into two parts
        """
        e = self.get_breaking_edge(breaking_edge_style)
        _LOG.debug("breaking_edge length = %s, %s" % (e.length, breaking_edge_style) )
        snl = self.n_leaves
        tree1, tree2 = self.bipartition_by_edge(e)
        _LOG.debug("Tree 1 has %s nodes, tree 2 has %s nodes" % (tree1.n_leaves, tree2.n_leaves) )
        assert snl == tree1.n_leaves + tree2.n_leaves
        return tree1, tree2

    def decompose_tree(self, maxSize=25, tree_map={}, strategy="centroid"):
        """
        This function decomposes the tree until all subtrees are smaller than the max size.  Two
        possible decompositions strategies can used: "centroid" and "longest".  Returns a
        map containing the subtrees, in an ordered fashion.
        
        SIDE EFFECT: deroots the tree (TODO: necessary?)
        """          
        self._tree.deroot()
        if (self.count_leaves() > maxSize):    
            (t1, t2) = self.bisect_tree(strategy)
            t1.decompose_tree(maxSize, tree_map, strategy)
            t2.decompose_tree(maxSize, tree_map, strategy)
        else:
            tree_map[len(tree_map)] = self
        return tree_map
    
    def lable_edges(self):
        en = 0        
        for e in self._tree.postorder_edge_iter():
            e.label = en
            en += 1

def node_formatter(n):
    return str(id(n))

def edge_formatter(e):
    return "%s %f " % (str(id(e)), e.length)

def is_valid_tree(t):
    assert t and t
    rc = t.seed_node.child_nodes()
    num_children = len(rc)
    if num_children == 0:
        return True
    if num_children == 1:
        assert not rc[0].child_nodes()
        return True
    if num_children == 2:
        assert((not rc[0].child_nodes()) and (not rc[0].child_nodes()))
    return True