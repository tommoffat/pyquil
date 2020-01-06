##############################################################################
# Copyright 2018 Rigetti Computing
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
##############################################################################
import warnings

from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Sequence, Union, Optional

from rpcq.messages import ParameterAref

from pyquil.api._error_reporting import _record_call


class QAMError(RuntimeError):
    pass


class QAM(ABC):
    """
    The platonic ideal of this class is as a generic interface describing how a classical computer
    interacts with a live quantum computer.  Eventually, it will turn into a thin layer over the
    QPU and QVM's "QPI" interfaces.

    The reality is that neither the QPU nor the QVM currently support a full-on QPI interface,
    and so the undignified job of this class is to collect enough state that it can convincingly
    pretend to be a QPI-compliant quantum computer.
    """

    @_record_call
    def __init__(self):
        self.reset()

    @_record_call
    def load(self, executable):
        """
        Initialize a QAM into a fresh state.

        :param executable: Load a compiled executable onto the QAM.
        """
        if self.status == "loaded":
            warnings.warn("Overwriting previously loaded executable.")
        assert self.status in ["connected", "done", "loaded"]

        self._variables_shim = {}
        self._executable = executable
        self._memory_results = defaultdict(lambda: None)
        self.status = "loaded"
        return self

    @_record_call
    def write_memory(self, *, region_name: str, offset: Optional[int] = None,
                     value: Optional[Union[int, float, Sequence[int],
                                           Sequence[float]]] = None):
        """
        Writes a value or unwraps a list of values into a memory region on
        the QAM at a specified offset.

        :param region_name: Name of the declared memory region on the QAM.
        :param offset: Integer offset into the memory region to write to.
        :param value: Value(s) to store at the indicated location.
        """
        assert self.status in ["loaded", "done"]

        if offset is None:
            offset = 0
        elif isinstance(value, Sequence):
            warnings.warn("offset should be None when value is a Sequence")

        if isinstance(value, Sequence):
            assert all(isinstance(v, type(value[0])) for v in value), \
                "Element of 'value' must be of uniform type"
            if region_name in self._variables_shim.keys() and len(value) > \
                    len(self._variables_shim[region_name]) - offset:
                raise ValueError('Value sequence exceeds memory region size')

            for index, v in enumerate(value):
                if not isinstance(v, type(value[0])):
                    raise TypeError('Value sequence is not of uniform type')

                aref = ParameterAref(name=region_name, index=offset + index)
                self._variables_shim[aref] = v
        else:
            aref = ParameterAref(name=region_name, index=offset)
            self._variables_shim[aref] = value

        return self

    @abstractmethod
    def run(self):
        """
        Reset the program counter on a QAM and run its loaded Quil program.
        """
        self.status = "running"

        return self

    @_record_call
    def wait(self):
        """
        Blocks until the QPU enters the halted state.
        """
        assert self.status == "running"
        self.status = "done"
        return self

    @_record_call
    def read_memory(self, *, region_name: str):
        """
        Reads from a memory region named region_name on the QAM.

        This is a shim over the eventual API and only can return memory from a region named
        "ro" of type ``BIT``.

        :param region_name: The string naming the declared memory region.
        :return: A list of values of the appropriate type.
        """
        assert self.status == "done"

        return self._memory_results[region_name]

    @_record_call
    def read_from_memory_region(self, *, region_name: str):
        """
        Reads from a memory region named region_name on the QAM.

        This is a shim over the eventual API and only can return memory from a region named
        "ro" of type ``BIT``.

        :param region_name: The string naming the declared memory region.
        :return: A list of values of the appropriate type.
        """
        warnings.warn(
            "pyquil.api._qam.QAM.read_from_memory_region is deprecated, please use "
            "pyquil.api._qam.QAM.read_memory instead.",
            DeprecationWarning,
        )

        return self.read_memory(region_name=region_name)

    @_record_call
    def reset(self):
        """
        Reset the Quantum Abstract Machine to its initial state, which is particularly useful
        when it has gotten into an unwanted state. This can happen, for example, if the QAM
        is interrupted in the middle of a run.
        """
        self._variables_shim = {}
        self._executable = None
        self._memory_results = defaultdict(lambda: None)
        self._experiment = None

        self.status = "connected"
