class SemanticGraphService:
    """
    Creates relationships between vocabulary.
    """

    def build_connections(self, words):

        connections = {}

        for word in words:

            connections[word] = []

            for other in words:

                if word != other and word[0] == other[0]:

                    connections[word].append(other)

        return connections
    
# TODO: integrate with semantic cluster service