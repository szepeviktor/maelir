#pragma once

#include "semaphore.hh"
#include "tile.hh"

#include <array>
#include <atomic>
#include <etl/deque.h>
#include <etl/mutex.h>
#include <etl/vector.h>

class ApplicationState
{
public:
    constexpr static auto kMaxStoredPositions = 4;

    class IListener
    {
    public:
        virtual ~IListener() = default;
    };

    struct State
    {
        virtual ~State() = default;

        bool demo_mode {false};
        bool gps_connected {false};
        bool bluetooth_connected {false};
        bool show_speedometer {true};

        IndexType home_position {0};
        etl::deque<IndexType, kMaxStoredPositions> stored_positions {};

        bool operator==(const State& other) const = default;
        State& operator=(const State& other) = default;
    };

    std::unique_ptr<IListener> AttachListener(os::binary_semaphore& semaphore);

    // Checkout a local copy of the global state. Rewritten when the unique ptr is released
    std::unique_ptr<State> Checkout();

    const State* CheckoutReadonly() const;

private:
    class ListenerImpl;
    class StateImpl;

    void Commit(const StateImpl* state);

    State m_global_state;
    etl::mutex m_mutex;
    etl::vector<ListenerImpl*, 4> m_listeners;
};
