cmake_minimum_required(VERSION 3.4.1)
set(CMAKE_CXX_STANDARD 17)

### INCLUDE OBOE LIBRARY ###

# Set the path to the Oboe library directory
set(PROJ_DIR ../..)
set(THIRDPARTY_DIR ${PROJ_DIR}/thirdparty)

include_directories(${THIRDPARTY_DIR}/argparse/include)

# App specific sources
set(APP_SOURCES
    replay_evdev.cc)

# Build the libpulsedroid-rtp library
add_executable(replay_evdev ${APP_SOURCES})

# Specify the libraries needed for hello-oboe
target_link_libraries(replay_evdev android log)

# Enable optimization flags: if having problems with source level debugging,
# disable -Ofast ( and debug ), re-enable after done debugging.
target_compile_options(replay_evdev PRIVATE -Wall -Werror "$<$<CONFIG:RELEASE>:-Ofast>")
