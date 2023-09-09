import os
from typing import Dict, List, Union

import numpy as np
from ..const import *
from ..utils import verify_load_inputs
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams

from .abstract import EmSearchBackend


class QdrantBackend(EmSearchBackend):
    """A search backend that uses a qdrant server to store and search embeddings"""

    def __init__(
        self,
        config: VectorParams = DEFAULT_QDRANT_CONFIG,
        collection: str = DEFAULT_COLLECTION_NAME,
        qdrant_host: str = DEFAULT_QDRANT_HOST,
        qdrant_port: int = DEFAULT_QDRANT_PORT,
    ):
        """
        Connect to Qdrant on commandline first:
        (Ubuntu Linux terminal)
        sudo docker run -p 6333:6333     -v $(pwd)/qdrant_storage:/qdrant/storage     qdrant/qdrant

        :param config: the vector parameter
        :param collection: name of collection
        """
        self.collection = collection
        self.config = config
        self.qd_client = QdrantClient(
            url=os.environ.get("QDRANT_HOST", qdrant_host),
            port=os.environ.get("QDRANT_PORT", qdrant_port),
            api_key=os.environ.get("QDRANT_API_KEY", None),
        )

        # Create collection only if it does not exist
        try: 
            collection_info = self.qd_client.get_collection(collection_name=self.collection)
            _LOGGER.info("Using collection {self.collection} with {collection_info.points_count} points"}}")
        except Exception:  # qdrant_client.http.exceptions.UnexpectedResponse
            _LOGGER.info(f"Collection {self.collection} does not exist, creating it")
            self.qd_client.recreate_collection(
                collection_name=self.collection, vectors_config=self.config
            )

    def load(self, embeddings: np.ndarray, labels: List[Dict[str, str]]):
        """
        upload vectors and their labels onto qdrant storage

        :param embeddings: embedding vectors of bed files, a np.ndarray with shape of (n, <vector size>)
        :param labels: list of dictionaries that contain information of the vectors to be store
        :return:
        """

        verify_load_inputs(embeddings, labels)

        start = len(self)
        points = [
            PointStruct(id=i + start, vector=embeddings[i].tolist(), payload=labels[i])
            for i in range(len(labels))
        ]
        self.qd_client.upsert(
            collection_name=self.collection,
            points=points,
        )

    def search(
        self, query: np.ndarray, k: int, with_payload: bool = True, with_vec: bool = True
    ) -> List[Dict[str, Union[int, float, Dict[str, str], List[float]]]]:
        """
         with a given query vector, get k nearest neighbors from vectors in the collection

        :param query: a vector to search
        :param k: number of returned results
        :param with_payload: whether payload is included in the result
        :param with_vec: whether the stored vector is included in the result
        :return: a list of dictionary that contains the search results in this format:
        {
            "id": <id>
            "score": <score>
            "payload": {
                <information of the vector>
            }
            "vector": [<the vector>]
        }
        """
        # KNN search in qdrant client
        search_results = self.qd_client.search(
            collection_name=self.collection,
            query_vector=query,
            limit=k,
            with_payload=with_payload,
            with_vectors=with_vec,
        )

        # add the results in to the output list
        output_list = []
        for result in search_results:
            # build each dictionary
            result_dict = {"id": result.id, "score": result.score}
            if with_payload:
                result_dict["payload"] = result.payload
            if with_vec:
                result_dict["vector"] = result.vector
            output_list.append(result_dict)
        return output_list

    def __len__(self) -> int:
        """
        Return the number of embeddings in the backend
        """
        return self.qd_client.get_collection(collection_name=self.collection).vectors_count

    def retrieve_info(
        self, ids: Union[List[int], int], with_vec: bool = False
    ) -> Union[
        Dict[str, Union[int, List[float], Dict[str, str]]],
        List[Dict[str, Union[int, List[float], Dict[str, str]]]],
    ]:
        """
        With a given list of storage ids, return the information of these vectors

        :param ids: list of ids, or a single id
        :param with_vec:  whether the vectors themselves will also be returned in the output
        :return: if ids is one id, a dictionary similar to the output of search() will be returned, without "score";
        if ids is a list, a list of dictionaries will be returned
        """
        if not isinstance(ids, list):
            # retrieve() only takes iterable input
            ids = [ids]
        output_list = []
        retrievals = self.qd_client.retrieve(
            collection_name=self.collection,
            ids=ids,
            with_payload=True,
            with_vectors=with_vec,  # no need vectors
        )
        # retrieve() of qd client does not return result in the order of ids in the list
        # sort it for convenience
        sorted_retrievals = sorted(retrievals, key=lambda x: ids.index(x.id))

        # get the information
        for result in sorted_retrievals:
            result_dict = {"id": result.id, "payload": result.payload}
            if with_vec:
                result_dict["vector"] = result.vector
            output_list.append(result_dict)

        # with just one id, only the dictionary instead of the list will be returned
        if len(output_list) == 1:
            return output_list[0]
        else:
            return output_list

    def __str__(self):
        return "QdrantBackend with {} items".format(len(self))

    def __repr__(self):
        return "QdrantBackend with {} items".format(len(self))
