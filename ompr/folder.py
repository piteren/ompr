from abc import abstractmethod
import logging
from pathlib import Path
from pypaq.lipytools.files import Folder, prep_folder
from pypaq.mpython.devices import DevicesPypaq
from typing import Iterable, Any

from ompr.runner import OMPRunner
from ompr.worker import RunningWorker

logger = logging.getLogger(__name__)


class RunningWorkerFolder(RunningWorker):
    """to be implemented by the user"""

    @abstractmethod
    def process(
            self,
            file_source_path: Path | str,
            file_target_path: Path | str,
            **kwargs,
    ) -> Any: pass


class FolderMP(Folder):

    def process_files_mp(
            self,
            rww_class: type[RunningWorkerFolder],
            path_processed: Path | str,
            add_ext: str | None = None,
            include: str | Iterable[str] | None = None,
            exclude: str | Iterable[str] | None = None,
            devices: DevicesPypaq = 'all',
            rww_init_kwargs: dict | None = None,
            report_interval: int = 60,
            **processing_func_kwargs,
    ):
        """processes all files in the Folder using MP"""

        logger.info(f"processing files ({len(self._files)}) with MP:")
        logger.info(f"> from {self._full_path}")
        logger.info(f"> to {path_processed}")
        logger.info(f"> with {rww_class.__class__.__name__}")
        if add_ext:
            logger.info(f">> adding ext: {add_ext}")
        if include:
            logger.info(f">> including {include}")
        if exclude:
            logger.info(f">> excluding {exclude}")

        files, files_target = self._get_paths_for_processing(
            path_processed=path_processed,
            add_ext=add_ext,
            include=include,
            exclude=exclude,
        )

        for fp in files_target:
            prep_folder(fp)

        ompr = OMPRunner(
            rww_class=rww_class,
            rww_init_kwargs=rww_init_kwargs if rww_init_kwargs else {},
            devices=devices,
            report_interval=report_interval,
            loglevel_subproc=30,  # 30 -> WARN
        )

        tasks = [
            {'file_source_path': fs, 'file_target_path': ft, **processing_func_kwargs}
            for fs, ft in zip(files, files_target)]
        ompr.process(tasks)
        ompr.get_all_results()
        ompr.exit()