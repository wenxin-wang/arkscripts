#include <fstream>
#include <iostream>

#include <sys/time.h>
#include <time.h>
#include <linux/input.h>

#include <argparse/argparse.hpp>

int main(int argc, char *argv[]) {
    argparse::ArgumentParser program("replay_evdev");
    program.add_argument("-d", "--device")
        .required()
        .help("specify the device to replay event into.");
    program.add_argument("-i", "--input")
        .required()
        .help("specify the input file.");
    try {
      program.parse_args(argc, argv);
    } catch (const std::runtime_error& err) {
      std::cout << err.what() << std::endl;
      std::cout << program;
      exit(0);
    }
    std::ifstream ifs(program.get<std::string>("-i"), std::ios_base::in | std::ios_base::binary);
    std::ofstream ofs(program.get<std::string>("-d"), std::ios_base::out | std::ios_base::binary);

    struct timeval replay_start_time, record_start_time;
    bool has_replay_start_time = false, has_record_start_time = false;

    while (ifs.good()) {
        struct input_event event;
#define IFS_READ(x) ifs.read((char*)&(x), sizeof(x))
        IFS_READ(event.time.tv_sec);
        IFS_READ(event.time.tv_usec);
        IFS_READ(event.code);
        IFS_READ(event.type);
        IFS_READ(event.value);
#undef IFS_READ
        // std::cout << "event " << event.time.tv_sec  << " " << event.time.tv_usec << " " << event.code << " " << event.type << " " << event.value << std::endl;
        struct timeval now_time;
        gettimeofday(&now_time, nullptr);
        if (!has_replay_start_time) {
            replay_start_time = now_time;
            has_replay_start_time = true;
        }
        if (!has_record_start_time) {
            record_start_time = event.time;
            has_record_start_time = true;
        }
        struct timeval time_diff;
        timersub(&event.time, &record_start_time, &time_diff);
        struct timeval next_time;
        timeradd(&replay_start_time, &time_diff, &next_time);
        if (timercmp(&next_time, &now_time, >)) {
            // std::cout << "sleep" << std::endl;
            timersub(&next_time, &now_time, &time_diff);
            struct timespec sleep_duration;
            sleep_duration.tv_sec = time_diff.tv_sec;
            sleep_duration.tv_nsec = time_diff.tv_usec * 1000;
            int ret = 0;
            do {
                struct timespec sleep_remain;
                ret = nanosleep(&sleep_duration, &sleep_remain);
                if (ret == -1) {
                    sleep_duration = sleep_remain;
                }
            } while (ret);
        } else {
            // std::cout << "non-sleep" << std::endl;
        }
#define OFS_WRITE(x) ofs.write((char*)&(x), sizeof(x))
        OFS_WRITE(next_time.tv_sec);
        OFS_WRITE(next_time.tv_usec);
        OFS_WRITE(event.code);
        OFS_WRITE(event.type);
        OFS_WRITE(event.value);
#undef OFS_WRITE
        ofs.flush();
    }
    return 0;
}
