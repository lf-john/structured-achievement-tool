import asyncio
import logging
import os
import time

logger = logging.getLogger(__name__)

FLUSH_INTERVAL = 0.5  # seconds
MIN_WRITE_SIZE = 100  # minimum chars before flushing


class StreamParser:
    def __init__(self, output_file: str, flush_interval: float = FLUSH_INTERVAL):
        self.output_file = output_file
        self.flush_interval = flush_interval
        self._buffer = ""
        self._last_flush = 0.0
        self._in_code_block = False
        self._code_block_depth = 0

    async def stream_process(self, process: asyncio.subprocess.Process) -> str:
        """Stream stdout from a subprocess to the output file. Returns full output."""
        full_output = []

        async for chunk in self._read_chunks(process.stdout):
            full_output.append(chunk)
            self._buffer += chunk
            self._update_code_block_state(chunk)

            if self._should_flush():
                self._flush_to_file()

        # Final flush
        if self._buffer:
            self._flush_to_file(force=True)

        return "".join(full_output)

    def feed(self, text: str):
        """Feed text into the parser (for non-async usage)."""
        self._buffer += text
        self._update_code_block_state(text)
        if self._should_flush():
            self._flush_to_file()

    def finalize(self):
        """Flush any remaining buffer."""
        if self._buffer:
            self._flush_to_file(force=True)

    def _should_flush(self) -> bool:
        """Determine if buffer should be flushed."""
        # Don't flush in the middle of a code block
        if self._in_code_block:
            return False
        now = time.time()
        time_ok = (now - self._last_flush) >= self.flush_interval
        size_ok = len(self._buffer) >= MIN_WRITE_SIZE
        return time_ok and size_ok

    def _flush_to_file(self, force: bool = False):
        """Write buffer to file."""
        if not self._buffer:
            return
        if self._in_code_block and not force:
            return

        with open(self.output_file, "a", encoding="utf-8") as f:
            f.write(self._buffer)
            f.flush()
            os.fsync(f.fileno())

        self._buffer = ""
        self._last_flush = time.time()

    def _update_code_block_state(self, text: str):
        """Track whether we're inside a markdown code block."""
        # Count ``` occurrences
        count = text.count("```")
        if count % 2 == 1:
            self._in_code_block = not self._in_code_block

    async def _read_chunks(self, stream, chunk_size: int = 1024):
        """Async generator to read chunks from a stream."""
        while True:
            chunk = await stream.read(chunk_size)
            if not chunk:
                break
            yield chunk.decode("utf-8", errors="replace")
