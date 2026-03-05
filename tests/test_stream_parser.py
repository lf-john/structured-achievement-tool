"""Tests for StreamParser — real-time Claude output streaming to Obsidian."""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.execution.stream_parser import MIN_WRITE_SIZE, StreamParser


@pytest.fixture
def tmp_output(tmp_path):
    """Return a temporary output file path."""
    return str(tmp_path / "response.md")


@pytest.fixture
def parser(tmp_output):
    """Return a StreamParser with a short flush interval for testing."""
    return StreamParser(tmp_output, flush_interval=0.0)


class TestFeedAndFlush:
    """Test feed() writes content to file when conditions are met."""

    def test_feed_writes_to_file_when_threshold_met(self, parser, tmp_output):
        """Feed enough text to exceed MIN_WRITE_SIZE and verify file write."""
        text = "A" * (MIN_WRITE_SIZE + 1)
        parser.feed(text)

        with open(tmp_output) as f:
            assert f.read() == text

    def test_feed_does_not_write_below_min_size(self, tmp_output):
        """Small feeds should buffer without writing (even with zero interval)."""
        # Use a non-zero flush interval so the time check fails on first feed
        p = StreamParser(tmp_output, flush_interval=999.0)
        p.feed("short")

        assert not os.path.exists(tmp_output)

    def test_multiple_feeds_accumulate(self, parser, tmp_output):
        """Multiple small feeds accumulate and flush together."""
        chunk = "B" * 60
        parser.feed(chunk)  # 60 chars — below MIN_WRITE_SIZE, stays in buffer
        parser.feed(chunk)  # 120 chars — above MIN_WRITE_SIZE, triggers flush

        with open(tmp_output) as f:
            assert f.read() == chunk * 2

    def test_feed_appends_on_subsequent_flushes(self, parser, tmp_output):
        """Each flush appends to the file, not overwrites."""
        block1 = "X" * (MIN_WRITE_SIZE + 1)
        block2 = "Y" * (MIN_WRITE_SIZE + 1)
        parser.feed(block1)
        parser.feed(block2)

        with open(tmp_output) as f:
            assert f.read() == block1 + block2


class TestCodeBlockDetection:
    """Test that flushing is suppressed inside markdown code blocks."""

    def test_no_flush_inside_code_block(self, tmp_output):
        """Buffer should not flush while inside an open code block."""
        p = StreamParser(tmp_output, flush_interval=0.0)
        text = "```python\n" + "x" * (MIN_WRITE_SIZE + 50)
        p.feed(text)

        # File should NOT exist because we're inside a code block
        assert not os.path.exists(tmp_output)

    def test_flush_after_code_block_closes(self, tmp_output):
        """Once the code block closes, the buffer should flush."""
        p = StreamParser(tmp_output, flush_interval=0.0)
        p.feed("```python\ncode\n```\n" + "Z" * MIN_WRITE_SIZE)

        with open(tmp_output) as f:
            content = f.read()
        assert "```python" in content
        assert "code" in content

    def test_nested_code_block_toggle(self, tmp_output):
        """Two ``` in one chunk cancel out (even count leaves state unchanged)."""
        p = StreamParser(tmp_output, flush_interval=0.0)
        # Two fences = even count, _in_code_block stays False
        p.feed("```python\ncode\n```\n" + "A" * MIN_WRITE_SIZE)

        with open(tmp_output) as f:
            assert len(f.read()) > 0


class TestFlushIntervalTiming:
    """Test flush interval gating with mocked time."""

    @patch("src.execution.stream_parser.time")
    def test_flush_respects_interval(self, mock_time, tmp_output):
        """Buffer should not flush before the interval elapses."""
        mock_time.time.return_value = 100.0
        p = StreamParser(tmp_output, flush_interval=5.0)
        p._last_flush = 100.0  # just flushed

        # Time hasn't advanced — should not flush even with enough data
        text = "D" * (MIN_WRITE_SIZE + 1)
        p._buffer = text
        assert not p._should_flush()

    @patch("src.execution.stream_parser.time")
    def test_flush_after_interval_elapsed(self, mock_time, tmp_output):
        """Buffer should flush once interval has passed."""
        mock_time.time.return_value = 106.0
        p = StreamParser(tmp_output, flush_interval=5.0)
        p._last_flush = 100.0

        p._buffer = "E" * (MIN_WRITE_SIZE + 1)
        assert p._should_flush()


class TestFinalize:
    """Test finalize() flushes remaining buffer."""

    def test_finalize_flushes_remaining_buffer(self, tmp_output):
        """Finalize should write whatever is left, regardless of size."""
        p = StreamParser(tmp_output, flush_interval=999.0)
        p._buffer = "leftover"
        p.finalize()

        with open(tmp_output) as f:
            assert f.read() == "leftover"

    def test_finalize_noop_on_empty_buffer(self, tmp_output):
        """Finalize with empty buffer should not create the file."""
        p = StreamParser(tmp_output, flush_interval=0.0)
        p.finalize()
        assert not os.path.exists(tmp_output)

    def test_finalize_flushes_inside_code_block(self, tmp_output):
        """Force-flush via finalize even if inside a code block."""
        p = StreamParser(tmp_output, flush_interval=0.0)
        p._buffer = "```python\nincomplete code"
        p._in_code_block = True
        p.finalize()

        with open(tmp_output) as f:
            assert "incomplete code" in f.read()


class TestForceFlushInCodeBlock:
    """Test that force=True overrides code block suppression."""

    def test_force_flush_writes_despite_code_block(self, tmp_output):
        """_flush_to_file(force=True) should write even in code block."""
        p = StreamParser(tmp_output, flush_interval=0.0)
        p._buffer = "```\nstuck content"
        p._in_code_block = True
        p._flush_to_file(force=True)

        with open(tmp_output) as f:
            assert f.read() == "```\nstuck content"

    def test_non_force_flush_blocked_in_code_block(self, tmp_output):
        """_flush_to_file(force=False) should NOT write in code block."""
        p = StreamParser(tmp_output, flush_interval=0.0)
        p._buffer = "```\nblocked content"
        p._in_code_block = True
        p._flush_to_file(force=False)

        assert not os.path.exists(tmp_output)


class TestStreamProcess:
    """Test the async stream_process method."""

    @pytest.mark.asyncio
    async def test_stream_process_collects_output(self, tmp_output):
        """stream_process should return full output and write to file."""
        p = StreamParser(tmp_output, flush_interval=0.0)

        # Create a mock process with async stdout
        mock_process = MagicMock()
        content = b"Hello world output " * 20  # enough to exceed MIN_WRITE_SIZE
        call_count = 0

        async def mock_read(size):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return content
            return b""

        mock_process.stdout.read = mock_read
        result = await p.stream_process(mock_process)

        assert result == content.decode('utf-8')
        with open(tmp_output) as f:
            assert f.read() == content.decode('utf-8')
