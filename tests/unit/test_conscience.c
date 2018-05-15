/*
Copyright (C) 2016-2017 OpenIO SAS, as part of OpenIO SDS

This library is free software; you can redistribute it and/or
modify it under the terms of the GNU Lesser General Public
License as published by the Free Software Foundation; either
version 3.0 of the License, or (at your option) any later version.

This library is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public
License along with this library.
*/

#include <glib.h>
#include <metautils/lib/metautils.h>
#include <cluster/module/server.h>

static void
test_restart_srv_from_file(void)
{
	/*
	//Restart from non-existing filename
	gboolean res = restart_srv_from_file("/somewhere");
	g_assert_false(res);

	//Create file with bad content
	gchar *path = "/tmp/conscience_persistence" ;
	gchar *content = "bad content";
	gssize length = 11;
	GError *err = NULL;
	g_file_set_contents(path, content, length, &err);

	//Restart from file with bad content
	res = restart_srv_from_file(path);
	g_assert_false(res);
	*/
}
 
static void
test_write_status(void)
{
        
}

int
main(int argc, char **argv)
{
	HC_TEST_INIT(argc,argv);
	g_test_add_func("/conscience/persistance/read", test_restart_srv_from_file);
	g_test_add_func("/conscience/persistance/write", test_write_status);        
}

