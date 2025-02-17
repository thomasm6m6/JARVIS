all:
	@echo nil

run:
	DYLD_LIBRARY_PATH=/opt/homebrew/opt/ffmpeg@6/lib:$(DYLD_LIBRARY_PATH) python3 server.py