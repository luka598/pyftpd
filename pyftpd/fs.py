import dataclasses as dc
import typing as T


@dc.dataclass
class BaseEntry:
    name: str


@dc.dataclass
class BaseFile(BaseEntry):
    size: int = dc.field(init=False, default=-1)

    def open(self) -> bool:
        raise NotImplementedError()

    def close(self) -> bool:
        raise NotImplementedError()

    def read(self) -> T.Tuple[bool, bytes]:
        raise NotImplementedError()

    def write(self, data: bytes) -> bool:
        raise NotImplementedError()


@dc.dataclass
class BaseDirectory(BaseEntry):
    parent_directory: T.Optional["BaseDirectory"] = None

    def get_subentries(self) -> T.List[BaseEntry]:
        raise NotImplementedError()


@dc.dataclass
class Filesystem:
    current_directory: BaseDirectory

    def _get_root(self) -> T.Tuple[BaseDirectory, T.Tuple[str, ...]]:
        root_dir = self.current_directory
        path = []
        while root_dir.parent_directory is not None:
            path.append(root_dir.name)
            root_dir = root_dir.parent_directory
        return root_dir, tuple(path)

    def get_path(self) -> str:
        _, path_tuple = self._get_root()
        print(path_tuple)
        path = "/" + "/".join(path_tuple[::-1])
        return path

    def change_path(self, path: str) -> bool:
        if len(path) == 0:
            return True

        path_parts = path.split("/")

        dest_directory = self.current_directory
        if path_parts[0] == "":
            dest_directory, _ = self._get_root()
            path_parts = path_parts[1:]

        for part in path_parts:
            subentries = dest_directory.get_subentries()
            dest_directory = next(
                (
                    entry
                    for entry in subentries
                    if (entry.name == part) and (isinstance(entry, BaseDirectory))
                ),
                None,
            )
            if dest_directory is None:
                return False
        self.current_directory = dest_directory
        return True


@dc.dataclass
class VirtualFile(BaseFile):
    _data: bytes = dc.field(default=b"")
    _is_open: bool = dc.field(init=False, default=False)

    def open(self) -> bool:
        if self._is_open:
            return False
        return True

    def close(self) -> bool:
        if not self._is_open:
            return False
        return True

    def read(self) -> T.Tuple[bool, bytes]:
        return True, self._data

    def write(self, data: bytes) -> bool:
        self._data = data
        return True


@dc.dataclass
class VirtualDirectory(BaseDirectory):
    _subentries: T.List[BaseEntry] = dc.field(default_factory=list)

    def get_subentries(self) -> T.List[BaseEntry]:
        return self._subentries

    def add_directory(self, directory: BaseDirectory) -> bool:
        directory.parent_directory = self
        self._subentries.append(directory)
        return True

    def add_file(self, file: BaseFile) -> bool:
        self._subentries.append(file)
        return True


if __name__ == "__main__":
    root_dir = VirtualDirectory("root")
    test_dir = VirtualDirectory("test")
    test_dir.add_directory(VirtualDirectory("isi"))
    root_dir.add_directory(test_dir)
    root_dir.add_file(VirtualFile("Test1"))
    root_dir.add_file(VirtualFile("Test2"))
    root_dir.add_file(VirtualFile("Test3"))
    fs = Filesystem(root_dir)
    print(fs.change_path("/test/isi"))
    print(fs.get_path())
