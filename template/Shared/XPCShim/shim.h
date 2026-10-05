#pragma once

// The SDK's own constants, handed to Swift as functions. See module.modulemap
// for why they cannot be named directly in Swift. Nothing is defined here;
// every body is an SDK macro, and every symbol behind them is in libSystem on
// every iOS that has XPC at all.
//
// Keep only the ones the project uses — an accessor nobody calls is a line to
// maintain — and add one when a call site needs it.

#include <xpc/xpc.h>
#include <xpc/connection.h>

static inline xpc_type_t app_xpc_type_array(void) { return XPC_TYPE_ARRAY; }
static inline xpc_type_t app_xpc_type_bool(void) { return XPC_TYPE_BOOL; }
static inline xpc_type_t app_xpc_type_connection(void) { return XPC_TYPE_CONNECTION; }
static inline xpc_type_t app_xpc_type_data(void) { return XPC_TYPE_DATA; }
static inline xpc_type_t app_xpc_type_dictionary(void) { return XPC_TYPE_DICTIONARY; }
static inline xpc_type_t app_xpc_type_error(void) { return XPC_TYPE_ERROR; }
static inline xpc_type_t app_xpc_type_int64(void) { return XPC_TYPE_INT64; }
static inline xpc_type_t app_xpc_type_string(void) { return XPC_TYPE_STRING; }
static inline xpc_type_t app_xpc_type_uint64(void) { return XPC_TYPE_UINT64; }

static inline size_t app_xpc_array_append(void) { return XPC_ARRAY_APPEND; }

static inline xpc_object_t app_xpc_error_connection_interrupted(void) {
    return XPC_ERROR_CONNECTION_INTERRUPTED;
}
static inline xpc_object_t app_xpc_error_connection_invalid(void) {
    return XPC_ERROR_CONNECTION_INVALID;
}
