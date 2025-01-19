#pragma once

#include "semaphore.hh"
#include "time.hh"

#include <array>
#include <etl/vector.h>
#include <functional>
#include <optional>

namespace os
{

constexpr auto kMaxTimers = 8;

class ITimer
{
public:
    virtual ~ITimer() = default;

    virtual bool IsExpired() const = 0;

    virtual milliseconds TimeLeft() const = 0;
};

class TimerManager
{
public:
    TimerManager(os::binary_semaphore& semaphore);

    std::unique_ptr<ITimer> StartTimer(milliseconds timeout,
                                       std::function<std::optional<milliseconds>()> on_timeout);

    std::optional<milliseconds> Expire();

private:
    class TimerImpl;

    struct Entry
    {
        milliseconds timeout;
        std::function<std::optional<milliseconds>()> on_timeout;
        TimerImpl* cookie;
        bool expired;
    };

    Entry &EntryAt(uint8_t index)
    {
        return m_timers[index];
    }

    os::binary_semaphore& m_semaphore;

    std::array<Entry, kMaxTimers> m_timers {};


    etl::vector<uint8_t, kMaxTimers> m_pending_removals;
    etl::vector<uint8_t, kMaxTimers> m_active_timers;
    etl::vector<uint8_t, kMaxTimers> m_free_timers;


    milliseconds m_last_expiery;
};

}; // namespace os
